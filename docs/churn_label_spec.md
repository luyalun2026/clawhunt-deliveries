# calib.churn_label 口径说明（S6-CAL-002）

## 1. 观察窗定义

以每个**月度快照日 t** 为起点，观察窗为 `(t, t+90]`（90 天，含第 90 天当日）。
每行输出 `observed_until = t + 90 天`。

## 2. 正例规则（2 条）

- **正例 R1（expiry_no_renewal）**：观察窗内会籍到期，且到期日后 **30 天内**未生成续约会籍（续约判定：存在另一会籍其 start 落在 `(expiry, expiry+30]` 内），记 `label=1`。
- **正例 R2（member_churned）**：观察窗内员工确认流失（生命周期变为「已流失」），记 `label=1`。

## 3. 排除规则（4 条）

- **排除 E1（in_onboarding）**：快照日处于入会引导期（距入会日不足 30 天），`label IS NULL`。
- **排除 E2（membership_terminated）**：快照日会籍已终止，`label IS NULL`。
- **排除 E3（window_open）**：观察窗尚未结束（`observed_until > 数据截止日`），`label IS NULL`，**不进入训练与评估集**。
- **排除 E4（non_recoverable）**：流失原因为**企业注销或迁出**，仍记 `label=1` 但 `label_reason=non_recoverable`；评估时同时报告**含与不含**该子集两种口径。

## 4. 判定优先级

E2 → E1 → E3 → R2 → R1 → `label=0 (retained)`。

## 5. 分组切分

同一企业多个快照全部保留，但训练/验证切分必须按 `company_pid` 整组切分
（`tools/split_by_company.py`），避免同一企业同时出现在训练集与验证集。

## 6. 双口径评估

正例统计区分「含 non_recoverable」与「不含 non_recoverable」两组，
评估指标（如 AUC）建议同时报告两种口径。

## 7. 存储

演示环境输出 SQLite 表 `churn_label`（列：company_pid、snapshot_date、label、label_reason、observed_until）；
PostgreSQL 版 DDL（schema calib）见 `pg_ddl.sql`，列定义一致。
