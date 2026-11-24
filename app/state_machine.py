"""状态机规则：最终级别在入队时由确定性规则决定并随响应返回。"""

# 级别从严到宽：L3 > L2 > L1
LEVELS = ["L3", "L2", "L1"]
LEVEL_INDEX = {name: idx for idx, name in enumerate(LEVELS)}

# requested_level -> confidence_score 门槛
THRESHOLDS = {"strict": 0.80, "standard": 0.60, "draft": 0.40}
ALLOWED_REQUESTED_LEVELS = tuple(THRESHOLDS.keys())

DRAFT_STATUSES = ("pending_review", "effective", "rejected", "expired")
EVENT_TYPE_BY_ACTION = {
    "effective": "ai.draft.effective",
    "rejected": "ai.draft.rejected",
    "expired": "ai.draft.expired",
}


# requested_level -> LEVELS 下标（strict 最严）
REQUESTED_LEVEL_INDEX = {"strict": 0, "standard": 1, "draft": 2}


def compute_final_level(requested_level: str, ai_content: dict) -> str:
    """最终级别规则：
    - confidence_score >= requested_level 门槛 -> 保留 requested 级别；
    - 低于门槛 -> 降一级（已在最低级则保持 L1）。
    """
    if requested_level not in ALLOWED_REQUESTED_LEVELS:
        raise ValueError(f"unknown requested_level: {requested_level}")
    score = float(ai_content.get("confidence_score", 0.0))
    idx = REQUESTED_LEVEL_INDEX[requested_level]
    if score >= THRESHOLDS[requested_level]:
        return LEVELS[idx]
    return LEVELS[min(idx + 1, len(LEVELS) - 1)]
