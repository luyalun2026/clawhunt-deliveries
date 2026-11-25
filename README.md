# S4-GO-029 · 会员主数据迁移核对脚本（交付页）

**交付物**：`scripts/reconcile_members.py`（单文件 CLI，只读，零第三方运行时依赖）

## 验收标准逐条对应（证据见 `evidence/`）

| # | 验收标准 | 结果 | 证据 |
|---|---|---|---|
| 1 | 6 类已知差异全部检出 | ✅ 12 条差异覆盖 missing / duplicate / many_to_one / field / credit_code_conflict / orphan_contact 全部 6 类 | `evidence/run_log.txt` 运行2、`evidence/diff_detail_sample.csv` |
| 2 | 差异 0 → 退出码 0，否则非 0 | ✅ 干净集 exit=0；差异集 exit=1；坏参数 exit=2（pytest 覆盖） | `evidence/run_log.txt` 运行1、`evidence/pytest.txt` |
| 3 | 明细 CSV 手机号全掩码 | ✅ 输出形如 `139****4014`，测试断言全文无手机号明文 | `evidence/diff_detail_sample.csv` 第 10 行 |
| 4 | 三条标准化规则各有单元测试 | ✅ strip / 全角转半角 / 手机号去国家码，4 个独立测试 | `evidence/pytest.txt` |
| 5 | 1000 企业 / 5000 联系人 < 2 分钟 | ✅ 实测 **10.92 s**（门槛 120 s） | `evidence/run_log.txt` 运行3 |

**pytest 汇总：12 passed in 15.18s**（含性能、退出码、掩码、边界用例）。

## 运行方法

```bash
# 干净集 → 退出码 0
python scripts/reconcile_members.py --source fixtures/clean --target fixtures/clean --out out_clean

# 6 类已知差异集 → 退出码 1，六类全检出
python scripts/reconcile_members.py --source fixtures/six_diffs --target fixtures/six_diffs/_target \
    --mapping fixtures/six_diffs/mapping.csv --out out_six

# 性能集（1000 企业 / 5000 联系人）
python scripts/reconcile_members.py --source fixtures/perf --target fixtures/perf/_target --out out_perf

# 测试
python -m pytest tests/ -v
```

参数：`--source` 源目录、`--target` 目标目录、`--mapping` 映射表（缺省按 source_id 直连）、
`--site` 限定站点、`--sample N` 抽样、`--out` 输出目录（`diff_report.md` + `diff_detail.csv`）。
生产对接 PostgreSQL：`--db "$DATABASE_URL"`（psycopg 只读适配，见标准化规则说明 §4）。

## 对接点（按统一约定先行用桩）

- 依赖 S2-CRM 的对象模型（企业/联系人/关系/标签）：当前以 CSV 导出桩 + 只读 DB 适配器实现，
  接入时仅需替换 `read_csv_dir` 的目标侧为 SQLAlchemy 查询，核对逻辑零改动（README 同步维护于仓库）。

## 数据与保密

全部测试数据为虚构（FICT 企业、91FICT 信用代码、139/138 假号段），交付物无客户名称，无真实个人信息。
