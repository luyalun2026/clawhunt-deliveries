"""字段字典单一事实源：字段名 → 定义 / 来源 / 取值范围 / 可空 / 单位。

check_dictionary.py 会拿它与数据库实际列双向比对；dictionary.md / .csv 由脚本渲染，
不手工维护。任何字段变更必须先改本文件，否则校验脚本退出码非 0。
"""
from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class FieldSpec:
    name: str
    group: str          # 维度 / 原始值 / 标准化分 / 汇总 / 系统
    definition: str
    source: str
    range: str
    nullable: bool
    unit: str = ""
    window_days: int | None = None


FIELDS: dict[str, FieldSpec] = {}


def add(spec: FieldSpec) -> None:
    FIELDS[spec.name] = spec


add(FieldSpec("snapshot_date", "维度", "快照所属月份，固定为每月 1 日",
              "build_snapshot.py 按运行月生成", "日期，day 必须为 01", False))
add(FieldSpec("company_pid", "维度", "企业假名 ID，HMAC-SHA256(uscc) 前 32 位十六进制",
              "pseudonym.pid(uscc)，不存 uscc 原文", "32 位十六进制字符串", False))
add(FieldSpec("site_code", "维度", "会所编码", "site.code", "已配置的会所编码枚举", False))
add(FieldSpec("industry_code", "维度", "国标行业代码：门类字母 + 大类两位",
              "crm_company.industry_code", r"^[A-Z][0-9]{2}$，如 I65", False))
add(FieldSpec("stage", "维度", "企业所处阶段快照", "crm_company.stage", "prospect/signing/active/at_risk/churned", False))
add(FieldSpec("membership_level", "维度", "会籍等级", "membership.level", "vip/standard/observer 等已配置枚举", False))
add(FieldSpec("tenure_days", "维度", "入会至快照日的天数", "crm_company.joined_at 与 snapshot_date 之差", ">=0 整数", False, "天"))
add(FieldSpec("days_to_expiry", "维度", "距会籍到期天数，已过期为负", "membership.expires_at 与 snapshot_date 之差", "整数，可负", False, "天"))

add(FieldSpec("event_raw", "原始值", "近 90 天活动签到次数", "event_checkin 计数", ">=0 整数或 NULL", True, "次", 90))
add(FieldSpec("interaction_raw", "原始值", "近 30 天有效互动次数", "有效互动事件（认证/发布/报名/签到/提问/对接）计数", ">=0 整数或 NULL", True, "次", 30))
add(FieldSpec("resource_raw", "原始值", "近 30 天资源大厅浏览、发布、响应次数合计", "resource_view + resource_publish + resource_response", ">=0 整数或 NULL", True, "次", 30))
add(FieldSpec("opportunity_raw", "原始值", "近 90 天商机阶段推进次数", "crm_opportunity_stage_log 计数", ">=0 整数或 NULL", True, "次", 90))
add(FieldSpec("space_raw", "原始值", "近 30 天空间使用小时数", "booking 使用时长合计", ">=0 小数或 NULL", True, "小时", 30))

for key, label in [
    ("event_score", "活动参与"),
    ("interaction_score", "互动活跃"),
    ("resource_score", "资源使用"),
    ("opportunity_score", "商机推进"),
    ("space_score", "空间使用"),
]:
    add(FieldSpec(key, "标准化分", f"{label}子项标准化分（与生产健康分同一套 normalize 函数）",
                  f"normalize({key.replace('_score', '_raw')})", "0–100，原始值为空时为 NULL", True, "分"))

add(FieldSpec("health_score", "汇总", "综合健康分", "各子项分加权求和后截断 [0,100]", "0–100 或 NULL", True, "分"))
add(FieldSpec("health_level", "汇总", "健康等级", "health_score 分档：A>=80, B>=60, C>=40, D<40", "A/B/C/D 或 NULL", True))
add(FieldSpec("computed_at", "系统", "本行写入时间", "数据库 now()", "时间戳", False))
add(FieldSpec("algorithm_version", "系统", "算法版本号，用于口径追溯", "build_snapshot.py 常量", "v1 等字符串", False))

BUSINESS_FIELD_NAMES = [k for k, v in FIELDS.items() if v.group in ("维度", "原始值", "标准化分")]


def as_dicts() -> list[dict]:
    return [asdict(FIELDS[name]) for name in FIELDS]


def render_markdown() -> str:
    lines = [
        "# calib.health_snapshot 数据字典",
        "",
        "> 本文件由 `tools/check_dictionary.py --render` 自动生成，请勿手工编辑。",
        f"> 业务字段 {len(BUSINESS_FIELD_NAMES)} 个，总字段 {len(FIELDS)} 个。",
        "",
        "| 字段 | 分组 | 定义 | 来源 | 取值范围 | 可空 | 单位 | 窗口(天) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name in FIELDS:
        f = FIELDS[name]
        lines.append(
            f"| `{f.name}` | {f.group} | {f.definition} | {f.source} | {f.range} | "
            f"{'是' if f.nullable else '否'} | {f.unit or '-'} | {f.window_days or '-'} |")
    return "\n".join(lines) + "\n"
