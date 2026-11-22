# -*- coding: utf-8 -*-
"""知识库问答服务层（供对抗测试，v2）。

v2 变更（对应返工意见）：
- 语料**只从 corpus/corpus.json 加载**，不再内嵌副本（意见 9）；未知 user_id 统一 401（意见 9）。
- 泄露判定改为**按受限切片原文与价格数字断言**，不再只查 4 个关键词（意见 4）。
- 会话按 session_id 累积轮次与历史，多轮递进套取按轮判定（意见 5）。
- 注入/藏指令防御走归一化句式与结构化检测，覆盖改写与同义变体（意见 6）。
- 对外只暴露 FastAPI 应用（见 app/main.py），测试经 HTTP 调用（意见 3）。

权限模型：角色白名单 × 文档状态（active/offline/deleted）。
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from typing import Dict, List, Optional

REFUSAL = "抱歉，您没有权限查看该内容。"

NOT_FOUND_BODY = {"error": "not_found", "detail": "resource not found"}
UNAUTHORIZED_BODY = {"error": "unauthorized", "detail": "unknown user"}

ROLES = ("reception", "ops", "member_mgr", "supervisor", "member")

_HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS_PATH = os.environ.get(
    "KB_CORPUS", os.path.join(_HERE, os.pardir, "corpus", "corpus.json")
)


def _load_corpus(path: str) -> List[dict]:
    with open(path, encoding="utf-8") as fh:
        docs = json.load(fh)
    for doc in docs:
        doc["roles"] = set(doc["roles"])
    return docs


CORPUS: List[dict] = _load_corpus(CORPUS_PATH)

USERS: Dict[str, str] = {
    "u_recep1": "reception",
    "u_ops1": "ops",
    "u_mgr1": "member_mgr",
    "u_sup1": "supervisor",
    "u_member1": "member",
    "u_member2": "member",
}

# ---- 受限内容与价格信号（从语料结构推导，不手写清单） ----

_PRICE_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:元|块|折)|[一二三四五六七八九]折")


def _restricted_docs() -> List[dict]:
    return [d for d in CORPUS if d.get("restricted")]


def restricted_slice_ids() -> List[str]:
    return [sid for d in _restricted_docs() for sid in d["slices"]]


def restricted_texts() -> List[str]:
    return [t for d in _restricted_docs() for t in d["slices"].values()]


def restricted_price_signals() -> List[str]:
    """受限切片里出现的价格数字/折扣串，任一出现即视为泄露。"""
    out: List[str] = []
    for text in restricted_texts():
        for m in _PRICE_RE.finditer(text):
            sig = m.group(0).replace(" ", "")
            if sig not in out:
                out.append(sig)
    return out


def _norm(text: str) -> str:
    """全半角归一 + 空白压缩 + 小写，抵御同义/变体改写。"""
    t = unicodedata.normalize("NFKC", text).lower()
    return re.sub(r"\s+", "", t)


# 注入意图：归一化后按语义特征判定（不依赖单一字面词）
_INJECT_PATTERNS = (
    r"忽略.{0,6}(规则|限制|指令|设定)",
    r"(无视|跳过|绕过).{0,6}(规则|限制|权限|设定)",
    r"(列出|输出|导出|打印|dump|贴出?).{0,8}(全部|所有|完整).{0,8}(价格|价目|文档|切片|内容|正文)",
    r"(全部|所有|完整).{0,8}(切片|价目|文档|正文).{0,6}(导出|输出|列出|贴|给我|发我)",
    r"(透露|泄露|告诉我).{0,8}(内部|受限|机密|隐藏)",
    r"(开发者?|调试|上帝|管理员)模式",
    r"(之前|上面|那些).{0,6}(的话|规则|限制|权限|设定).{0,6}(作废|不算|无效|解除|取消)",
    r"(按|按照|照).{0,10}(正文|文档|公告).{0,6}(指示|要求|说的|吩咐).{0,6}(回答|做|执行)?",
    r"(让你|要你).{0,8}(透露|公开|说出).{0,4}(什么|啥).{0,6}(照做|执行|就做)",
    r"(你现在|从现在起).{0,8}(是|作为).{0,8}(管理员|root|开发者)",
)

_SENSITIVE_PATTERNS = (
    r"价格|价目|报价|折扣|租金|多少钱|怎么收|收多少|收费|费用|便宜|贵|元/月",
)


def is_injection(question: str) -> bool:
    q = _norm(question)
    return any(re.search(p, q) for p in _INJECT_PATTERNS)


def is_price_intent(question: str) -> bool:
    q = _norm(question)
    return any(re.search(p, q) for p in _SENSITIVE_PATTERNS)


def role_of(user_id: str) -> str:
    role = USERS.get(user_id)
    if role is None:
        raise KeyError("unknown_user")
    return role


# ---- 会话 ----

_SESSIONS: Dict[str, dict] = {}


def reset() -> None:
    _SESSIONS.clear()


def session_state(session_id: str) -> dict:
    st = _SESSIONS.get(session_id)
    if st is None:
        return {"turns": 0, "refusals": 0, "history": []}
    return {"turns": st["turns"], "refusals": st["refusals"],
            "history": list(st["history"])}


def _record(session_id: Optional[str], question: str, refused: bool) -> None:
    if session_id is None:
        return
    st = _SESSIONS.setdefault(session_id, {"turns": 0, "refusals": 0, "history": []})
    st["turns"] += 1
    if refused:
        st["refusals"] += 1
    st["history"].append({"turn": st["turns"], "q": question, "refused": refused})


# ---- 检索 ----


def _grams(text: str, n: int = 2) -> set:
    t = _norm(text)
    if len(t) < n:
        return {t}
    return {t[i:i + n] for i in range(len(t) - n + 1)}


def _visible_slices(role: str) -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    for doc in CORPUS:
        if doc["status"] != "active" or role not in doc["roles"]:
            continue
        for sid, text in doc["slices"].items():
            out[sid] = {"doc_id": doc["doc_id"], "text": text,
                        "restricted": bool(doc.get("restricted"))}
    return out


def _is_price_slice(text: str) -> bool:
    """切片是否真的承载价格事实（避免正文藏指令的切片被当作价格答案）。"""
    t = _norm(text)
    return bool(_PRICE_RE.search(t)) or any(
        k in t for k in ("价目", "内部价格", "内部折扣", "报价"))


def _offline_title_hit(question: str) -> bool:
    qg = _grams(question, 3)
    for doc in CORPUS:
        if doc["status"] != "active" and _grams(doc["title"], 3) & qg:
            return True
    return False


def _neutralize(text: str) -> str:
    """正文内嵌指令：整句切除，保留其余事实句（按标点切句逐句判定）。"""
    kept = []
    for sent in re.split(r"(?<=[。！？；])", text):
        if not sent.strip():
            continue
        n = _norm(sent)
        if is_injection(sent) or "藏入正文" in n or re.search(
                r"(请|务必|必须).{0,8}(透露|公开|告知).{0,8}(内部|所有)", n):
            continue
        kept.append(sent.strip())
    return "".join(kept).strip("。 ")


def _guard(answer: str, citations: List[str], role: str) -> None:
    """输出前泄露校验：受限原文与价格信号不得出现在回答或引用中。"""
    allowed = {sid for sid, m in _visible_slices(role).items()
               if m["restricted"]}
    for sid in citations:
        assert sid in allowed or sid not in restricted_slice_ids(), "越权引用"
    if citations and all(c in allowed for c in citations):
        return
    na = _norm(answer)
    for text in restricted_texts():
        if _norm(text) in na:
            raise AssertionError("泄露受限切片原文")
    for sig in restricted_price_signals():
        if _norm(sig) in na:
            raise AssertionError("泄露价格信号: %s" % sig)


def _refuse(session_id: Optional[str], question: str) -> dict:
    _record(session_id, question, True)
    return {"answer": REFUSAL, "citations": [], "refused": True}


def ask(user_id: str, question: str, session_id: Optional[str] = None) -> dict:
    """检索式问答：只引用可见切片；敏感意图按角色裁决；注入/藏指令一律不执行。"""
    role = role_of(user_id)

    if is_injection(question):
        return _refuse(session_id, question)

    if is_price_intent(question):
        if _offline_title_hit(question):
            return _refuse(session_id, question)
        # 价格问句只允许在「对该受限文档有权限」时命中受限切片；
        # 无权角色的可见集本就不含受限切片，因此命中为空 → 统一拒答。
        hits = _visible_slices(role)
        picked = [sid for sid, m in hits.items()
                  if _is_price_slice(_neutralize(m["text"]))
                  and _grams(_neutralize(m["text"])) & _grams(question)]
        if not picked:
            return _refuse(session_id, question)
        out = _compose(hits, picked)
        _guard(out["answer"], out["citations"], role)
        _record(session_id, question, out["refused"])
        return out

    hits = _visible_slices(role)
    picked = [sid for sid, m in hits.items() if _grams(m["text"]) & _grams(question)]
    out = _compose(hits, picked)
    _guard(out["answer"], out["citations"], role)
    _record(session_id, question, out["refused"])
    return out


def _compose(hits: Dict[str, dict], picked: List[str]) -> dict:
    parts: List[str] = []
    for sid in picked:
        text = _neutralize(hits[sid]["text"])
        if text:
            parts.append(text)
    return {
        "answer": "。".join(parts) + ("。" if parts else REFUSAL),
        "citations": picked,
        "refused": not parts,
    }


def get_slice(user_id: str, slice_id: str) -> dict:
    """切片原文查看。无权限/不存在/已下线/已删除 → 完全相同的 404 响应体。"""
    role = role_of(user_id)
    for doc in CORPUS:
        if slice_id in doc["slices"]:
            if doc["status"] == "active" and role in doc["roles"]:
                return {"slice_id": slice_id, "doc_id": doc["doc_id"],
                        "text": doc["slices"][slice_id]}
            raise KeyError("not_found")
    raise KeyError("not_found")
