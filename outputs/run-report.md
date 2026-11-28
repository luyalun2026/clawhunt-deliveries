# 运行报告（自动生成）

- 生成时间：2026-11-28T22:46:46
- 命令：`python verify.py`（内部 `pytest tests -q` + `python probe.py`）
- pytest 汇总：`46 passed in 1.94s`；退出码 0
- 用例 46，通过 46，失败 0

## 用例 × 结果矩阵

| 验收分组 | 用例数 | 通过 | 失败 | 结论 |
|---|---|---|---|---|
| AC1 拒答文案与固定文案逐字一致（含阈值边界） | 6 | 6 | 0 | 通过 |
| AC2 拒答路径生成模型调用次数为 0 | 6 | 6 | 0 | 通过 |
| AC3 每次拒答调用一次知识缺口记录 | 7 | 7 | 0 | 通过 |
| AC4 三类禁答各 ≥3 用例并通过 | 10 | 10 | 0 | 通过 |
| 边界与加固：可见范围/引用归一化/配置校验/政策优先级 | 12 | 12 | 0 | 通过 |
| 其他（边界与加固） | 5 | 5 | 0 | 通过 |
| **合计** | **46** | **46** | **0** | **全部通过** |

## 实测指标（probe.py 运行期提取）

- `cases` = `7`
- `refused` = `6`
- `answered` = `1`
- `generator_calls` = `1`
- `gap_calls` = `6`
- `outcome_matrix` = `{"normal": "answer/None", "low_score": "refuse_kb/low_score", "stale": "refuse_kb/stale_docs", "policy_contact": "refuse_policy/policy", "policy_business": "refuse_policy/policy", "policy_commitment": "refuse_policy/policy", "cross_site": "refuse_kb/insufficient"}`
- `rules_loaded` = `4`

## 口径说明

- 用例数与通过率由 junit.xml 解析得到，未人工填写。
- 指标由 probe.py 在真实执行路径中采集，写入 outputs/metrics.json 后并入本报告。
- 判定顺序：政策 → 可见范围 → 三条证据硬条件 → 生成 → 引用校验，短路即返回，生成只在最后一步发生一次。
- test_12 断言引用校验失败时总调用仍为 1 次（降级不走二次生成）。
- test_27 用全角数字与半角片段验证 NFKC 归一化后判通过，避免把等价文本误拒。
- test_29/30 用 monkeypatch 清空环境变量，验证缺省值与 used_defaults 记录。
