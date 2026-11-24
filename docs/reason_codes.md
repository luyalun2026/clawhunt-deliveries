# reason code 列表（归属判定）

| status | reason_code | 触发条件 | 返回字段 |
|---|---|---|---|
| `accepted` | — | 通过全部校验与查重，写入 prospect_keys | `report_id`、`rule_version`、`accepted_at`、`protection_until` |
| `rejected_invalid` | `MISSING_SUBJECT` | 统一社会信用代码与完整企业名均为空 | `report_id`、`status`、`reason_code` |
| `rejected_invalid` | `MISSING_CONTACT` | 联系人手机号缺失或不是 11 位大陆手机号 | 同上 |
| `rejected_invalid` | `SELF_REFERRAL` | 客户企业 USCC 与报备方自身 USCC 相同 | 同上 |
| `rejected_reporter_inactive` | `REPORTER_SUSPENDED` | 渠道方暂停 | 同上 |
| `rejected_reporter_inactive` | `REPORTER_TERMINATED` | 渠道方终止 | 同上 |
| `rejected_reporter_inactive` | `REPORTER_DISABLED` | 转介绍人停用 | 同上 |
| `rejected_reporter_inactive` | `REPORTER_NOT_FOUND` | 报备方不存在或已软删除 | 同上 |
| `rejected_existing_customer` | `EXISTING_MEMBER` | CRM 中为在籍会员 | 同上 |
| `rejected_existing_customer` | `CHURNED_WITHIN_12M` | 12 个月内退会（含第 365 天） | 同上 |
| `rejected_existing_customer` | `FOLLOWED_WITHIN_60D` | 60 天内有员工跟进记录（含第 60 天） | 同上 |
| `rejected_duplicate` | `DUPLICATE_USCC` | USCC 命中 active prospect_keys | `matched_key`、`first_reported_at`（**不含首单报备方任何身份字段**） |
| `rejected_duplicate` | `DUPLICATE_NAME` | 归一化企业名命中 | 同上 |
| `rejected_duplicate` | `DUPLICATE_PHONE` | 手机号哈希命中 | 同上 |
| `expired` | — | 每日任务：保护期到期且无签约进展 | 由 `expire_due()` 计数返回 |

## 判定顺序

1. 基本校验（主体、手机号）→ 2. 报备方资格 → 3. 自荐 → 4. 存量客户 →
5. 查重 → 6. 事务内写入 + 部分唯一索引兜底 → 7. 锁定规则版本、计算保护期。

## 身份隔离约定

重复拒绝只返回 `matched_key`（命中的键类型）与 `first_reported_at`（该键最早的报备时间），
不返回首单的 `report_id`、`reporter_id`、`reporter_name`、`contact_phone`。
`test_16` 与 `test_17` 对响应做字段白名单与敏感串扫描。
