# S4-FIN-011 银行到账流水导入与多模板字段映射

交付模板映射、CSV/xlsx 读取、Decimal 转分、去重与借方过滤、批次与流水模型、导入服务与测试。

## 运行

```bash
pip install -r requirements.txt
python -m pytest tests -q      # 12 passed（含 5000 行 60s 性能用例）
```

## 接口与服务

- `import_rows(session, rows, template, account_no, filename=...)` → `BankImportBatch`（计数：`added` / `skipped_dup` / `skipped_debit` / `failed` / `errors` / `elapsed_ms`）。
- 目标接口：`POST /api/finance/bank-imports`（multipart 上传，后台线程执行，立即返回 batch_id）、`GET /api/finance/bank-imports/{id}`（状态与错误行号）。

## 模板

模板存 `bank_statement_templates`：`columns` 为 JSON（交易日期/金额/借贷方向/对方户名/对方账号/附言/银行流水号 → 源列名）、`date_formats`、`encoding`、`amount_sign_rule`。新增银行只加一行配置，不改代码。

样例：银行 A（CSV，列名「交易日期/金额/借贷标志/…」）、银行 B（xlsx，列名「记账日/发生额/收付方向/…」）。

## 金额与方向

- 金额全程 `Decimal`：剥千分位/全角/货币符号/空格 → `Decimal` → `quantize(0.01)` → 整数分。`"1,234.56"→123456`、`"0.01"→1`、`"(56.70)"→-5670`、`"￥100.00"→10000`。
- 方向列优先（银行常见「金额恒正 + 方向列」）：`贷/收入/进账` 入库，`借/支出/出账` 计 `skipped_debit`；`贷 + 负数` 判为矛盾行计入 `failed`；无方向列时才用金额符号。
- 去重键 `(account_no, bank_serial)`：批内先聚合，跨批查库 + 唯一约束兜底。

## 性能

流式读取 + 批量插入，5000 行实测 0.3–1.5s（门槛 60s）。`timing.log` 记录 `rows / elapsed_ms / wall_ms / added / skipped_debit`。

## 验收对照

| 验收项 | 证据 |
|---|---|
| 两模板各自导入成功、金额逐分正确 | `test_template_a_import_amounts_and_counts`（SN001=123456、SN002=1、SN005=50000）、`test_template_b_xlsx_import` |
| 重复导入新增 0 | `test_duplicate_file_zero_new`：二次 `added=0`、`skipped_dup=4`、库内 3 行不变 |
| 借方不导入 | `test_debit_never_persisted`：SN003/SN004 不在库内 |
| 5000 行 < 60s | `test_5000_rows_under_60s`：4500 贷记入 + 500 借方跳过，断言 `elapsed < 60` |

## 边界另测

空文件/仅表头、缺列、`2026/1/5` 与 `20260105` 日期、脏金额逐行报错（行号与原因）、批内重复流水号、超 5000 行拒绝、流水号为空拒绝、xlsx 数字/日期单元格归一。
