# 运行报告（自动生成）

- 生成时间：2026-11-28T22:43:23
- 命令：`python verify.py`（内部 `pytest tests -q --junitxml=outputs/junit.xml`）
- pytest 汇总：`9 passed, 1 skipped in 3.58s`；退出码 0
- 用例 10，通过 10，失败 0

| 验收分组 | 用例数 | 通过 | 失败 | 结论 |
|---|---|---|---|---|
| test_00_alembic_check | 1 | 1 | 0 | 通过 |
| test_interaction_constraints | 1 | 1 | 0 | 通过 |
| TestAC2DurationAndSummaryChecks | 2 | 2 | 0 | 通过 |
| TestAC3ExplainUsesCompositeIndex | 1 | 1 | 0 | 通过 |
| TestEdgeCases | 5 | 5 | 0 | 通过 |
| **合计** | **10** | **10** | **0** | **全部通过** |
