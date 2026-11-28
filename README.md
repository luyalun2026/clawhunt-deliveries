# 工单 #1935 · 证据充分性判定与拒答规则

## 运行结果

- 用例 41，通过 41，失败 0（41 passed in 1.81s）
- 生成时间：2026-11-22T02:22:30

| 验收分组 | 用例数 | 通过 | 失败 | 结论 |
|---|---|---|---|---|
| AC1 拒答文案与固定文案逐字一致（含阈值边界） | 6 | 6 | 0 | 通过 |
| AC2 拒答路径生成模型调用次数为 0 | 6 | 6 | 0 | 通过 |
| AC3 每次拒答调用一次知识缺口记录 | 7 | 7 | 0 | 通过 |
| AC4 三类禁答各 ≥3 用例并通过 | 10 | 10 | 0 | 通过 |
| 边界与加固：可见范围/引用归一化/配置校验/政策优先级 | 12 | 12 | 0 | 通过 |
| **合计** | **41** | **41** | **0** | **全部通过** |

## 实测指标（probe.py 运行期采集）

| 指标 | 实测值 |
|---|---|
| `cases` | `7` |
| `refused` | `6` |
| `answered` | `1` |
| `generator_calls` | `1` |
| `gap_calls` | `6` |
| `outcome_matrix` | `{"normal": "answer/None", "low_score": "refuse_kb/low_score", "stale": "refuse_kb/stale_docs", "policy_contact": "refuse_policy/policy", "policy_business": "refuse_policy/policy", "policy_commitment": "refuse_policy/policy", "cross_site": "refuse_kb/insufficient"}` |
| `rules_loaded` | `4` |

## 判定规则表（阈值 / 分支 / 文案 / 副作用）

| # | 条件 | 判定 | 文案来源 | 副作用 |
|---|---|---|---|---|
| 1 | 命中禁答三类（contact / business / commitment） | `refuse_policy` | `POLICY_TEXTS[category]` | 记 1 次知识缺口，`reason=policy`；不判分数 |
| 2 | 可见范围过滤后无切片 | `refuse_kb` | `REFUSAL_TEXT`（固定） | 记 1 次缺口，`reason=insufficient` |
| 3 | `max(rerank) < KB_MIN_RERANK_SCORE` | `refuse_kb` | `REFUSAL_TEXT` | 记 1 次缺口，`reason=low_score` |
| 4 | 达标切片数 `< KB_MIN_EVIDENCE` | `refuse_kb` | `REFUSAL_TEXT` | 记 1 次缺口，`reason=insufficient` |
| 5 | 达标切片全部 `doc_review_valid_until < today` | `refuse_kb` | `REFUSAL_TEXT` | 记 1 次缺口，`reason=stale_docs` |
| 6 | 生成后引用校验失败（chunk 不存在 / 片段不匹配） | `refuse_kb` | `REFUSAL_TEXT` | 记 1 次缺口，`reason=citation_failed`；整答降级 |
| 7 | 以上全部不命中 | `answer` | 生成结果 | 不记缺口；判定结果以 `review_level=L0` 进复核队列 |

固定文案：`知识库中没有找到；已记录为知识缺口，负责人会补充。`（`app/refusal.py: REFUSAL_TEXT`，测试按字面量比对，不做包含匹配）。

## 关键实现

- `app/settings.py`：`KB_MIN_RERANK_SCORE`（默认 0.35）、`KB_MIN_EVIDENCE`（1）、`DOC_FRESHNESS_DAYS`（180）、`KB_GAP_BASE_URL` 全部从环境变量读取，缺省时在 `used_defaults` 中留痕（test_29）。
- `app/refusal.py`：`decide()` 为短路流水线，生成模型只在第 7 步发生一次；`verify_citations()` 用 NFKC 归一化后做子串比对，全角/半角等价文本不会被误拒（test_27）。
- `app/policy.py` + `forbidden_rules.yaml`：正则 + 关键词双通道；加载时校验 `id` 唯一、每类规则样例 ≥3、三类齐全，缺失即启动报错（test_31 / test_32）。
- `stub/generator.py`：强制引用模式，可注入 `fake_chunk_id` / 改写片段，用于证明"引用失败必降级"。
- `stub/gap_service.py`：知识缺口服务桩（内存计数 + 请求体可查），生产替换为 `KB_GAP_BASE_URL` 指向的真实服务。

## 与其他工单的对接点

| 上游/下游 | 对接方式 |
|---|---|
| 重排服务 | 提供 `rerank_score`（0–1），未归一化时按 README 的线性归一化适配点处理 |
| 可见范围过滤 | 本模块接收 `site_id` / `user_level` / `deleted_at` / `classification` 字段自行过滤，也可由上游预过滤后只传可见切片 |
| 知识缺口服务（S3-KB-025） | `POST {KB_GAP_BASE_URL}`，载荷 `{question, reason, site_id, asked_at, category?}` |
| 生成服务 | 强制引用模式，返回 `{answer, citations:[{chunk_id, snippet}]}` |
| 复核队列 | 判定结果带 `review_level=L0` 入库，不对外发送 |

## 复现方式

```bash
pip install pytest pyyaml
python verify.py          # 跑 pytest + probe，生成 outputs/verify.json / matrix.md / run-report.md
cat outputs/run-report.md
```

依赖：Python 3.11+、pytest 9、PyYAML。无需网络、无需数据库、无境外接口。

## 边界与已知限制

- 每轮按独立 question 判定，不做多轮上下文继承（真实业务若需多轮，需在会话层拼接后传入）。
- `doc_review_valid_until` 缺失时视为不过期（fail-open），因为上游时效治理配置未就绪时把全部文档判过期会导致可用性归零；如需 fail-closed，改 `is_stale()` 一行即可。
- 政策判定基于规则词表，不做语义模型判定；词表由 `forbidden_rules.yaml` 维护，扩展无需改代码。
