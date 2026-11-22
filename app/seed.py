# -*- coding: utf-8 -*-
"""金丝雀种子数据与街道中心点（全部为虚构数据，不含任何真实个人信息/企业信息）。"""
from __future__ import annotations

# ---- 金丝雀联系方式（格式合法、可识别的虚构值）----
# 每家企业一组独立金丝雀；这些值一旦出现在任何 /api/mini/ 响应中即为泄露。
CANARY_COMPANIES = [
    {
        "id": "cm-0001", "name": "虚构测试企业壹号", "industry": "软件服务",
        "org_id": "org-0001", "site_id": "site-0001", "street_id": "st-0101",
        "mobile": "13812340001", "landline": "027-88888001",
        "email": "canary0001@example-fake.cn", "wechat": "wx_fake_0001",
        # 内部保存的“真实”精确坐标（远远超出街道级精度，响应中绝不允许出现）
        "lat": 30.5123456789, "lng": 114.3123456789,
    },
    {
        "id": "cm-0002", "name": "虚构测试企业贰号", "industry": "智能硬件",
        "org_id": "org-0002", "site_id": "site-0002", "street_id": "st-0102",
        "mobile": "13912340002", "landline": "027-88888002",
        "email": "canary0002@example-fake.cn", "wechat": "wx_fake_0002",
        "lat": 30.5234567891, "lng": 114.3234567891,
    },
    {
        "id": "cm-0003", "name": "虚构测试企业叁号", "industry": "设计咨询",
        "org_id": "org-0003", "site_id": "site-0003", "street_id": "st-0103",
        "mobile": "13712340003", "landline": "027-88888003",
        "email": "canary0003@example-fake.cn", "wechat": "wx_fake_0003",
        "lat": 30.5345678912, "lng": 114.3345678912,
    },
    {
        "id": "cm-0004", "name": "虚构测试企业肆号", "industry": "文创传媒",
        "org_id": "org-0004", "site_id": "site-0004", "street_id": "st-0101",
        "mobile": "13612340004", "landline": "027-88888004",
        "email": "canary0004@example-fake.cn", "wechat": "wx_fake_0004",
        "lat": 30.5456789123, "lng": 114.3456789123,
    },
    {
        "id": "cm-0005", "name": "虚构测试企业伍号", "industry": "贸易服务",
        "org_id": "org-0005", "site_id": "site-0005", "street_id": "st-0102",
        "mobile": "13512340005", "landline": "027-88888005",
        "email": "canary0005@example-fake.cn", "wechat": "wx_fake_0005",
        "lat": 30.5567891234, "lng": 114.3567891234,
    },
]

# 金丝雀联系人（挂在企业下的虚构联系人，作为第二种金丝雀形态）
CANARY_CONTACTS = [
    {"id": "ct-0001", "company_id": "cm-0001", "name": "测试联系人甲",
     "mobile": "15812340001", "email": "ct0001@example-fake.cn"},
    {"id": "ct-0002", "company_id": "cm-0002", "name": "测试联系人乙",
     "mobile": "15812340002", "email": "ct0002@example-fake.cn"},
    {"id": "ct-0003", "company_id": "cm-0003", "name": "测试联系人丙",
     "mobile": "15812340003", "email": "ct0003@example-fake.cn"},
]

# ---- 街道中心点（map_streets，恰好 4 位小数；会员端坐标只允许精确等于这些值）----
MAP_STREETS = [
    {"id": "st-0101", "name": "虚构珞喻路街道", "lat": 30.5123, "lng": 114.3123},
    {"id": "st-0102", "name": "虚构光谷大道街道", "lat": 30.5234, "lng": 114.3234},
    {"id": "st-0103", "name": "虚构关山街道", "lat": 30.5345, "lng": 114.3345},
    {"id": "st-0104", "name": "虚构金融港街道", "lat": 30.5456, "lng": 114.3456},
]

STREET_BY_ID = {s["id"]: s for s in MAP_STREETS}

# 街道下的虚构地图点位（内部坐标精确；响应只回街道中心点）
MAP_POINTS = [
    {"id": "pt-1001", "name": "壹号创新楼", "street_id": "st-0101", "raw_lat": 30.5123451, "raw_lng": 114.3123451},
    {"id": "pt-1002", "name": "贰号产业园", "street_id": "st-0102", "raw_lat": 30.5234452, "raw_lng": 114.3234452},
    {"id": "pt-1003", "name": "叁号孵化器", "street_id": "st-0103", "raw_lat": 30.5345453, "raw_lng": 114.3345453},
    {"id": "pt-1004", "name": "肆号会展中心", "street_id": "st-0104", "raw_lat": 30.5456454, "raw_lng": 114.3456454},
    {"id": "pt-1005", "name": "伍号联合办公", "street_id": "st-0101", "raw_lat": 30.5123461, "raw_lng": 114.3123461},
    {"id": "pt-1006", "name": "陆号人才公寓", "street_id": "st-0102", "raw_lat": 30.5234462, "raw_lng": 114.3234462},
]

NOTICES = [
    {"id": "nt-0001", "title": "平台服务细则更新（虚构）",
     "body": "会员企业可在工作台查看最新的入驻指引与服务清单。如有疑问请通过站内消息联系运营同事。",
     "published_at": "2026-11-01T09:00:00"},
    {"id": "nt-0002", "title": "十一月资源对接会通知（虚构）",
     "body": "本月对接会将于园区会展中心举行，报名通道已开放，名额有限，先到先得。",
     "published_at": "2026-11-10T09:00:00"},
    {"id": "nt-0003", "title": "场地预约系统升级公告（虚构）",
     "body": "预约系统将于周日凌晨例行升级，升级期间暂停服务两小时，请合理安排使用时间。",
     "published_at": "2026-11-15T09:00:00"},
]

# ---- 会员（含内部联系方式；响应模型中绝不允许出现这些字段）----
MEMBERS = {
    "mb-0001": {"id": "mb-0001", "display_name": "会员测试用户A", "company_id": "cm-0001",
                "role": "member", "status": "active",
                "mobile": "18612340001", "email": "mb0001@example-fake.cn", "wechat": "wx_mb_0001"},
    "mb-0002": {"id": "mb-0002", "display_name": "会员测试用户B", "company_id": "cm-0001",
                "role": "admin", "status": "active",
                "mobile": "18612340002", "email": "mb0002@example-fake.cn", "wechat": "wx_mb_0002"},
}


def all_canary_values() -> list[str]:
    """汇总全部金丝雀值（手机号/座机/邮箱/微信号），供响应扫描逐值比对。"""
    vals: list[str] = []
    for c in CANARY_COMPANIES:
        vals += [c["mobile"], c["landline"], c["email"], c["wechat"]]
    for ct in CANARY_CONTACTS:
        vals += [ct["mobile"], ct["email"]]
    for m in MEMBERS.values():
        vals += [m["mobile"], m["email"], m["wechat"]]
    return vals
