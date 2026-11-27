# #2430 交付包：多会所字段覆盖扫描（org_id / site_id 与索引核查）

## 运行方法（干净机器可复跑）

```bash
env -u GITHUB_TOKEN git clone --depth 1 --branch 2430 https://github.com/luyalun2026/clawhunt-deliveries.git
cd clawhunt-deliveries/2430
pip install sqlalchemy pytest
python -m pytest tests -q                                  # 6 例全绿
DATABASE_URL=postgresql://... python scan_tenancy_columns.py \
    --rules tenancy_rules.yaml --schema public \
    --report-md outputs/report.md --report-json outputs/report.json
echo $?    # 有 blocker 时为 1（可接入 CI）
```

## 交付物清单

| 文件 | 说明 |
|---|---|
| scan_tenancy_columns.py | 扫描脚本：information_schema.columns / pg_indexes / 约束目录实查（PG）；SQLite 走 pragma 等价目录（测试路径）。Markdown + JSON 双报告，blocker 退出码 1 |
| tenancy_rules.yaml | 分类规则：会所级 site / 机构级共享 org / 全局字典 global，分类依据逐表登记；未登记表一律 blocker |
| outputs/report.md / report.json | 对测试 schema（7 表）的实跑报告样例：blocker=2（fake_room 缺 site_id、sneaky_table 未登记）、major=3 |
| tests/test_scan.py | 6 例：AC1 数量与系统目录一致、AC2 两张虚构测试表两类问题均报出、AC3 未登记表 blocker + 退出码 1、全局字典豁免 |

## 验收对应

1. **AC1**：`scan()` 统计与系统目录（PG=information_schema.tables；SQLite 测试路径=sqlite_master 同口径）一致，测试断言相等。
2. **AC2**：`fake_room`（缺 site_id 列）与 `fake_venue`（缺 org_id 索引）两张虚构测试表，两类问题均被报出（blocker / major 分级）。
3. **AC3**：`sneaky_table` 未在 yaml 登记 → 标 blocker；存在 blocker 时退出码 1，有测试。

## 数字来源声明

报告中的业务表数量、缺失字段、缺失索引全部由 SQL 目录查询自动生成，零手写。

## 验证记录（本机实跑转录）

```
$ python -m pytest tests -q
......        [100%]
6 passed in 1.87s

$ python scan_tenancy_columns.py（对测试 schema）
exit-code equivalent: 1
{"blocker": 2, "major": 3, "warn": 0}
```
