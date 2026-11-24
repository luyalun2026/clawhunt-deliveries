# S4-FIN-019 财务软件对接：应收与实收凭证明细导出

交付两类明细导出（xlsx / CSV UTF-8 BOM）、科目映射表、期间锁定、调整明细与导出审计。

## 运行

```bash
pip install -r requirements.txt
python -m pytest tests -q      # 14 passed
```

```python
from app.finance.export_service import export, seed_mappings
seed_mappings(session, [("场地费", "6001.01", "1122.01", "2221.01"),
                        ("服务费", "6001.02", "1122.02", "2221.02")])
res = export(session, period="2026-11", export_type="receivable", fmt="xlsx",
             data=receivables, operator="finance01", out_dir="samples")
```

## 明细与列

**应收确认**：合同编号、企业、费用类型、所属期间、不含税金额(分)/(元)、税额(分)/(元)、价税合计(分)/(元)、收入科目、应收科目、税额科目、标记、原值(分)、差额(分)。

**实收核销**：银行流水号、到账日期、企业、核销分期、核销金额(分)/(元)、标记、原值(分)、差额(分)。

金额先转字符串再落盘：分列为整数（`#,##0`），元列为 `分/100` 两位小数（`#,##0.00`），不经 float。行内恒等式 `不含税 + 税额 = 价税合计` 不成立即拒导并报出错行。

## 期间锁定与调整明细

1. 首次导出：写 `export_snapshots`（每行 row_key + 金额）、`period_locks`、1 条 `export_runs`。
2. 再次导出：逐行比对快照 —
   - 未变：原样输出、标记空；
   - 变更：保留原行 + 追加**调整行**（金额=差额、标记=`已导出期间变更`、原值、差额）；
   - 新增：`标记=新增`；
   - 快照有而本次无：输出**冲销**行（金额取负）。
3. 科目映射缺失：抛 `MissingMapping`，错误体列出缺失费用类型，不产生半成品文件。

## 审计

每次导出写 1 条 `export_runs`：期间、类型、格式、行数、合计分、文件 sha256、操作人、是否含调整、时间。

## 验收对照

| 验收项 | 证据 |
|---|---|
| 两类明细合计与回款报表一致 | `test_receivable_totals_match_report`（6 笔合计 1,440,000 分）、`test_receipt_totals_match_report`（4 笔合计 980,000 分）；每行恒等式单独断言 |
| 已导出期间修改后生成调整明细 | `test_adjustment_generated_after_modification`：300000→290000，调整行差额 -10000、原值 300000、标记命中 |
| 映射缺失即失败并列出费用类型 | `test_missing_mapping_fails_with_fee_types`：`missing == ["广告费"]` |
| 每次导出 1 条审计 | `test_audit_row_per_export`：导出 3 次 → 3 行，字段完整 |

## 边界另测

空期间（仅表头、合计 0、仍写审计）、跨期核销排除、免税行 tax=0、金额 0 调整行、CSV BOM（`EF BB BF`）、xlsx 金额格式、同期间重复导出仅 1 条锁且 `first_exported_at` 不变。
