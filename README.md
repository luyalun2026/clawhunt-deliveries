# 2143 · S6-CAL-002 流失标签口径、观察窗定义与标签生成脚本

## 运行方法

```bash
pip install -r requirements.txt   # 仅标准库（无第三方依赖，占位）
python -m pytest tests -q         # 8 例测试
python build_churn_labels.py --input fixtures/timelines.json --db churn.db --stats output/monthly_stats.csv
python tools/split_by_company.py --input fixtures/timelines.json
```

## 交付物

- `build_churn_labels.py`：主脚本，输出 `calib.churn_label`（SQLite 演示存储）与每月样本统计表
- `docs/churn_label_spec.md`：口径说明（2 正例规则 + 4 排除规则 + 观察窗 + 双口径）
- `pg_ddl.sql`：PostgreSQL 16 版 DDL（schema calib）
- `tools/split_by_company.py`：按企业分组切分（防跨集泄漏）
- `fixtures/timelines.json`：10 家虚构企业手工时间线
- `tests/`：AC1 手算对账 / AC2 观察窗排除 / AC3 口径文档结构 / 边界 5 例

## 验收标准落点

| AC | 证据 |
|---|---|
| 1 手工时间线一致 | `test_ac1_hand_timelines_match`：13 行逐格与手算 CSV 一致 |
| 2 观察窗未结束 label 为空 | `test_ac2_window_open_null_and_excluded`：收紧截止日后全部 NULL 且不进评估集 |
| 3 口径文档 2+4 规则 | `test_ac3_spec_counts`：文档含 2 正例 + 4 排除规则条目 |

## 边界用例

到期后第 30/31 天续约判定、observed_until 恰等于截止日、快照日=入会第 30 天、流失事件恰在 t+90、企业分组切分无泄漏。

## 对接点（接口桩）

输入为 JSON 时间线文件（`fixtures/timelines.json`），正式接入时替换为 S2-CRM 读取层；PG 版表结构见 `pg_ddl.sql`。
