# -*- coding: utf-8 -*-
"""loop4 场景常量：构造数据与断言期望值的唯一来源（同源，杜绝手抄不一致）。"""

# 有效互动定义（验收口径）：不含纯浏览
INTERACTION_TYPES = ["auth", "demand", "signup", "checkin", "ask"]
# 提问中转人工的子类型
ASK_ESCALATED = "ask_escalated"

# 场景主体
ENT_A = {"id": "ent-A-0001", "name": "虚构会员企业甲", "site_id": "S1"}
ENT_B = {"id": "ent-B-0002", "name": "虚构会员企业乙", "site_id": "S1"}
MEMBER_U1 = {"id": "mem-U1-0001", "name": "会员一", "enterprise_id": "ent-A-0001", "deleted": False}
MEMBER_U2 = {"id": "mem-U2-0002", "name": "会员二", "enterprise_id": "ent-B-0002", "deleted": False}
MEMBER_UD = {"id": "mem-UD-0003", "name": "已删会员", "enterprise_id": "ent-A-0001", "deleted": True}

# 活动
ACTIVITY_1 = {"id": "act-0001", "title": "虚构活动一"}
ACTIVITY_2 = {"id": "act-0002", "title": "虚构活动二"}

# 期望的 6 项计数（企业 A / 会员 U1，均为当月、source=mini）
EXPECTED_COUNTS = {
    "certified_contacts": 1,   # 认证联系人数
    "demands": 1,              # 发布需求数
    "signups": 2,              # 报名数
    "checkins": 1,             # 签到数（重复签到去重后）
    "asks": 3,                 # 管家提问数
    "escalations": 1,          # 转人工数
}

# 月活：分子包含 ENT_A（有有效互动），排除 ENT_B（只浏览）
EXPECTED_MAU_ACTIVE_ENTS = ["ent-A-0001"]
EXPECTED_MAU_EXCLUDED_ENTS = ["ent-B-0002"]
