# -*- coding: utf-8 -*-
"""证据充分性判定与拒答：先政策、再可见范围、再证据三条硬条件、最后引用校验。

设计约束：
- 拒答路径绝不调用生成模型（decide 里生成只在全部条件通过后发生一次）。
- 每次拒答调用且仅调用一次知识缺口服务。
- 判定为纯函数 + 注入的 Settings/Generator/GapRecorder，便于逐分支断言。
"""
from datetime import date, datetime, timedelta

# 固定文案：主句「知识库中没有找到」+ 附句「已记录为知识缺口，负责人会补充」，
# 两段均与任务原文引号内字符串逐字一致，句号分隔，测试按字面量比对
REFUSAL_TEXT = "知识库中没有找到。已记录为知识缺口，负责人会补充"

POLICY_TEXTS = {
    "contact": "无法提供其他会员的联系方式，此类信息不对第三方开放。",
    "business": "无法提供其他会员的经营信息，此类信息不对第三方开放。",
    "commitment": "无法对价格或合同条款作出承诺，具体条款以正式合同为准。",
    "other": "该问题不在可回答范围内。",
}

REASON_PRIORITY = ("policy", "insufficient", "low_score", "stale_docs", "citation_failed")


class Decision:
    __slots__ = ("status", "answer", "reason", "evidence", "gap_recorded", "generator_calls", "review_level")

    def __init__(self, status, answer=None, reason=None, evidence=None,
                 gap_recorded=False, generator_calls=0, review_level="L0"):
        self.status = status
        self.answer = answer
        self.reason = reason
        self.evidence = evidence or []
        self.gap_recorded = gap_recorded
        self.generator_calls = generator_calls
        self.review_level = review_level

    def __repr__(self):
        return "Decision(status=%r, reason=%r)" % (self.status, self.reason)


def _today():
    return date.today()


def _as_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def visible_chunks(chunks, site_id, user_level=2):
    """只保留可见范围内的切片：同 site、未软删、密级不高于用户级。"""
    out = []
    for c in chunks:
        if c.get("deleted_at"):
            continue
        if c.get("site_id") != site_id:
            continue
        if int(c.get("classification", 1)) > int(user_level):
            continue
        out.append(c)
    return out


def evidence_ok(chunk, settings):
    return float(chunk.get("rerank_score", 0.0)) >= settings.min_rerank_score


def is_stale(chunk, settings, today=None):
    valid_until = _as_date(chunk.get("doc_review_valid_until"))
    if valid_until is None:
        return False
    return valid_until < (today or _today())


def verify_citations(answer_text, citations, chunks):
    """引用必须能在给定切片里找到（chunk_id 命中 + 原文片段归一化后为子串）。"""
    import unicodedata

    def norm(s):
        return unicodedata.normalize("NFKC", str(s or "")).replace(" ", "").replace("\n", "")

    pool = {c["chunk_id"]: norm(c.get("text", "")) for c in chunks}
    bad = []
    for cite in citations or []:
        cid = cite.get("chunk_id")
        snippet = norm(cite.get("snippet", ""))
        if cid not in pool:
            bad.append({"chunk_id": cid, "why": "chunk_not_found"})
            continue
        if snippet and snippet not in pool[cid]:
            bad.append({"chunk_id": cid, "why": "snippet_mismatch"})
    return (len(bad) == 0), bad


def decide(question, chunks, *, site_id, settings, policy_router, gap, generator,
           user_level=2, today=None):
    """返回 Decision。生成模型至多被调用一次，且只在放行路径上。"""
    # 1) 政策优先（命中即拒答，不做分数判定，避免文案混淆）
    policy_hit = policy_router(question)
    if policy_hit:
        gap.record(question=question, reason="policy", site_id=site_id, category=policy_hit)
        return Decision("refuse_policy", answer=POLICY_TEXTS.get(policy_hit, POLICY_TEXTS["other"]),
                        reason="policy", gap_recorded=True, generator_calls=0)

    # 2) 可见范围过滤（过滤掉的切片不参与任何计数）
    vis = visible_chunks(chunks, site_id=site_id, user_level=user_level)
    good = [c for c in vis if evidence_ok(c, settings)]
    fresh = [c for c in good if not is_stale(c, settings, today=today)]
    stale_all = [c for c in vis if is_stale(c, settings, today=today)]

    # 3) 三条硬条件（按 切片不足 > 全过期 > 低分 > 混合不足 的顺序给出 reason；
    #    全部可见切片过复审期时判 stale_docs（规则 5），即使它们同时全部低分）
    reason = None
    if not vis:
        reason = "insufficient"
    elif len(fresh) < max(1, int(settings.min_evidence)):
        if len(stale_all) == len(vis):
            reason = "stale_docs"
        elif not good:
            reason = "low_score"
        elif not fresh:
            reason = "stale_docs"
        else:
            reason = "insufficient"

    if reason:
        gap.record(question=question, reason=reason, site_id=site_id)
        return Decision("refuse_kb", answer=REFUSAL_TEXT, reason=reason,
                        evidence=[], gap_recorded=True, generator_calls=0)

    # 4) 放行：生成（强制引用）+ 引用校验，失败整体降级为拒答
    result = generator(question=question, chunks=fresh)
    calls = int(getattr(generator, "calls", 1))
    ok, bad = verify_citations(result.get("answer", ""), result.get("citations", []), fresh)
    if not ok:
        gap.record(question=question, reason="citation_failed", site_id=site_id)
        return Decision("refuse_kb", answer=REFUSAL_TEXT, reason="citation_failed",
                        evidence=[], gap_recorded=True, generator_calls=calls)

    return Decision("answer", answer=result.get("answer", ""), reason=None,
                    evidence=[c["chunk_id"] for c in fresh], gap_recorded=False,
                    generator_calls=calls)
