# -*- coding: utf-8 -*-
"""簇摘要：代表用例由程序选（距中心最近 + max-min 贪心），LLM 只写名称与说明。

名称 ≤40 字、说明 ≤120 字；超限先截断并记 truncated=true，同时按 meta.yaml 允许一次
带纠正提示的重试；重试仍超限则用截断值。数字（簇大小、排名）从不经过 LLM。
"""
import math

from app.embed import cosine

NAME_LIMIT = 40
DESC_LIMIT = 120
MAX_RETRY = 1


def centroid(vecs):
    n = len(vecs)
    dim = len(vecs[0])
    acc = [0.0] * dim
    for v in vecs:
        for i, x in enumerate(v):
            acc[i] += x
    norm = math.sqrt(sum(x * x for x in acc)) or 1.0
    return [x / norm for x in acc]


def pick_representatives(vecs, k=3):
    """返回代表点的下标：先取最近中心者，再按「与已选最小距离最大」补齐。"""
    c = centroid(vecs)
    dists = [1.0 - cosine(v, c) for v in vecs]
    order = sorted(range(len(vecs)), key=lambda i: (dists[i], i))
    picked = [order[0]]
    while len(picked) < min(k, len(vecs)):
        best_i, best_score = None, -1.0
        for i in range(len(vecs)):
            if i in picked:
                continue
            score = min(1.0 - cosine(vecs[i], vecs[j]) for j in picked)
            if score > best_score:
                best_i, best_score = i, score
        picked.append(best_i)
    return picked


def _clip(text, limit):
    text = (text or "").strip().replace("\n", " ")
    return text[:limit]


def summarize_cluster(excerpts, llm, name_limit=NAME_LIMIT, desc_limit=DESC_LIMIT):
    """excerpts: 代表用例的失败描述列表。llm: callable(excerpts, hint) -> {name, description}。"""
    attempts = []
    out = llm(excerpts, None)
    attempts.append({"hint": None, "name_len": len(out.get("name") or ""),
                     "desc_len": len(out.get("description") or "")})
    name = _clip(out.get("name"), name_limit)
    desc = _clip(out.get("description"), desc_limit)
    truncated = (name != (out.get("name") or "").strip()) or (desc != (out.get("description") or "").strip())

    if truncated and MAX_RETRY:
        hint = "名称不超过 %d 字，说明不超过 %d 字，不要换行。" % (name_limit, desc_limit)
        out2 = llm(excerpts, hint)
        attempts.append({"hint": hint, "name_len": len(out2.get("name") or ""),
                         "desc_len": len(out2.get("description") or "")})
        name2 = _clip(out2.get("name"), name_limit)
        desc2 = _clip(out2.get("description"), desc_limit)
        truncated2 = (name2 != (out2.get("name") or "").strip()) or (desc2 != (out2.get("description") or "").strip())
        # 重试若合规则采用重试值；仍不合规则保留首次截断值
        if not truncated2:
            name, desc, truncated = name2, desc2, False
        attempts[-1]["accepted"] = not truncated2

    return {"name": name, "description": desc, "truncated": truncated, "attempts": attempts}


def stub_llm(excerpts, hint=None):
    """离线 LLM 桩：按代表用例的关键词给出名称/说明；hint 存在时返回超短版本。"""
    joined = " ".join(excerpts)
    table = [
        ("得分", "阈值边界未命中", "评测点得分低于判定阈值，未达到命中条件。"),
        ("参数类型", "工具参数类型错误", "工具调用参数类型与 Schema 不符，被拒绝执行。"),
        ("拒答", "越权问句未拒答", "越权问句未触发政策拒答，直接给出了受限信息。"),
        ("引用悬空", "引用悬空无出处", "回答引用的片段不在给定切片中，无法回查。"),
    ]
    for key, name, desc in table:
        if key in joined:
            if hint:
                return {"name": name[:20], "description": desc[:60]}
            return {"name": name, "description": desc}
    if hint:
        return {"name": "零散失败", "description": "未归类失败。"}
    return {"name": "零散失败（环境与偶发）", "description": "未能归入任何密度簇的零星失败，需人工逐条判断是否为环境噪声。"}
