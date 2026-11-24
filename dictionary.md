# calib.health_snapshot 数据字典

> 本文件由 `tools/check_dictionary.py --render` 自动生成，请勿手工编辑。
> 业务字段 18 个，总字段 22 个。

| 字段 | 分组 | 定义 | 来源 | 取值范围 | 可空 | 单位 | 窗口(天) |
|---|---|---|---|---|---|---|---|
| `snapshot_date` | 维度 | 快照所属月份，固定为每月 1 日 | build_snapshot.py 按运行月生成 | 日期，day 必须为 01 | 否 | - | - |
| `company_pid` | 维度 | 企业假名 ID，HMAC-SHA256(uscc) 前 32 位十六进制 | pseudonym.pid(uscc)，不存 uscc 原文 | 32 位十六进制字符串 | 否 | - | - |
| `site_code` | 维度 | 会所编码 | site.code | 已配置的会所编码枚举 | 否 | - | - |
| `industry_code` | 维度 | 国标行业代码：门类字母 + 大类两位 | crm_company.industry_code | ^[A-Z][0-9]{2}$，如 I65 | 否 | - | - |
| `stage` | 维度 | 企业所处阶段快照 | crm_company.stage | prospect/signing/active/at_risk/churned | 否 | - | - |
| `membership_level` | 维度 | 会籍等级 | membership.level | vip/standard/observer 等已配置枚举 | 否 | - | - |
| `tenure_days` | 维度 | 入会至快照日的天数 | crm_company.joined_at 与 snapshot_date 之差 | >=0 整数 | 否 | 天 | - |
| `days_to_expiry` | 维度 | 距会籍到期天数，已过期为负 | membership.expires_at 与 snapshot_date 之差 | 整数，可负 | 否 | 天 | - |
| `event_raw` | 原始值 | 近 90 天活动签到次数 | event_checkin 计数 | >=0 整数或 NULL | 是 | 次 | 90 |
| `interaction_raw` | 原始值 | 近 30 天有效互动次数 | 有效互动事件（认证/发布/报名/签到/提问/对接）计数 | >=0 整数或 NULL | 是 | 次 | 30 |
| `resource_raw` | 原始值 | 近 30 天资源大厅浏览、发布、响应次数合计 | resource_view + resource_publish + resource_response | >=0 整数或 NULL | 是 | 次 | 30 |
| `opportunity_raw` | 原始值 | 近 90 天商机阶段推进次数 | crm_opportunity_stage_log 计数 | >=0 整数或 NULL | 是 | 次 | 90 |
| `space_raw` | 原始值 | 近 30 天空间使用小时数 | booking 使用时长合计 | >=0 小数或 NULL | 是 | 小时 | 30 |
| `event_score` | 标准化分 | 活动参与子项标准化分（与生产健康分同一套 normalize 函数） | normalize(event_raw) | 0–100，原始值为空时为 NULL | 是 | 分 | - |
| `interaction_score` | 标准化分 | 互动活跃子项标准化分（与生产健康分同一套 normalize 函数） | normalize(interaction_raw) | 0–100，原始值为空时为 NULL | 是 | 分 | - |
| `resource_score` | 标准化分 | 资源使用子项标准化分（与生产健康分同一套 normalize 函数） | normalize(resource_raw) | 0–100，原始值为空时为 NULL | 是 | 分 | - |
| `opportunity_score` | 标准化分 | 商机推进子项标准化分（与生产健康分同一套 normalize 函数） | normalize(opportunity_raw) | 0–100，原始值为空时为 NULL | 是 | 分 | - |
| `space_score` | 标准化分 | 空间使用子项标准化分（与生产健康分同一套 normalize 函数） | normalize(space_raw) | 0–100，原始值为空时为 NULL | 是 | 分 | - |
| `health_score` | 汇总 | 综合健康分 | 各子项分加权求和后截断 [0,100] | 0–100 或 NULL | 是 | 分 | - |
| `health_level` | 汇总 | 健康等级 | health_score 分档：A>=80, B>=60, C>=40, D<40 | A/B/C/D 或 NULL | 是 | - | - |
| `computed_at` | 系统 | 本行写入时间 | 数据库 now() | 时间戳 | 否 | - | - |
| `algorithm_version` | 系统 | 算法版本号，用于口径追溯 | build_snapshot.py 常量 | v1 等字符串 | 否 | - | - |
