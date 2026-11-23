# 运行报告（自动生成）

- 生成时间：2026-11-23T22:57:01
- 命令：`python verify.py`（内部 `pytest tests -q`，指标在本进程内实测）
- pytest 汇总：`20 passed in 30.12s`；退出码 0
- 用例 20，通过 20，失败 0，跳过 0

## 用例 × 结果矩阵

| 验收分组 | 用例数 | 通过 | 失败 | 结论 |
|---|---|---|---|---|
| AC1 10 种子生成变体覆盖 6 类技术且带溯源（统计输出） | 3 | 3 | 0 | 通过 |
| AC2 相似度超 0.9 的变体被丢弃（含跨种子、正反例） | 5 | 5 | 0 | 通过 |
| AC3 pending 目录 / promote 抽检准入 / CLI 可用 | 4 | 4 | 0 | 通过 |
| AC5 同义改写走本地模型 + 地址白名单 | 3 | 3 | 0 | 通过 |
| AC6 编码绕过子类均基于种子内容（含谐音） | 1 | 1 | 0 | 通过 |
| 边界：多轮拆分轮数 | 1 | 1 | 0 | 通过 |
| AC4 变体全部通过 eval-lint 与 eval-pii-scan | 3 | 3 | 0 | 通过 |
| **合计** | **20** | **20** | **0** | **全部通过** |

## 实测指标（本进程内实测）

- `seed_count` = `10`
- `variant_count` = `133`
- `dropped_by_dedupe` = `17`
- `per_technique` = `{"synonym_rewrite": 20, "roleplay_wrap": 20, "encoding_bypass": 34, "language_switch": 20, "multi_turn_split": 19, "pressure_wrap": 20}`
- `lint_passed` = `133`
- `pii_passed` = `133`
- `duplicate_pairs_over_0_9` = `0`

## 口径说明

- 用例数与通过率由 junit.xml 解析得到，未人工填写。
- 指标由 verify.py 在真实执行路径中采集，写入 outputs/metrics.json 后并入本报告。
- 全部内容虚构；种子为演示护栏用例（GUARD-001~010，对应 EVAL-025~028 系列口径）。
- 相似度口径：字符 trigram Jaccard 或归一化编辑距离任一 > 0.9 即判过近并丢弃；比较范围含全部种子与整批已保留变体（跨种子）。
- 生成模型地址从 REDTEAM_MODEL_BASE_URL 读取，默认拒绝，仅放行本机/私有网段/内网与 .cn 后缀；缺省或境外 fail-fast。
- 生成结果落盘 evals/suites/guardrail.variants.pending/pending.json；promote 从该目录读取，抽检率 >=10% 才写入 guardrail.regression.json。
