# 运行报告（自动生成）

- 生成时间：2026-11-22T19:51:31
- 命令：`python verify.py`（内部 `pytest tests -q` + `python probe.py`）
- pytest 汇总：`9 passed, 1 warning in 3.85s`；退出码 0
- 用例 9，通过 9，失败 0

## 用例 × 结果矩阵

| 验收分组 | 用例数 | 通过 | 失败 | 结论 |
|---|---|---|---|---|
| AC1 全流程步骤成功或跳过 | 1 | 1 | 0 | 通过 |
| AC2 重试耗尽置 failed | 1 | 1 | 0 | 通过 |
| AC3 重跑只跑指定步骤及下游 | 3 | 3 | 0 | 通过 |
| AC4 同项目并发触发 409 | 2 | 2 | 0 | 通过 |
| 迁移与模型（SQLAlchemy 2 / Alembic） | 2 | 2 | 0 | 通过 |
| **合计** | **9** | **9** | **0** | **全部通过** |

## 实测指标（probe.py 运行期提取）

- `happy_path` = `{"status": "succeeded", "total_jobs": 10, "succeeded": 9, "skipped": 1, "step_calls": {"preprocess": 1, "transcribe": 1, "diarize": 1, "postprocess": 1, "detect_sensitive": 1, "push_review": 1, "generate": 3}, "job_statuses": ["skipped", "succeeded"]}`
- `retry_exhausted` = `{"status": "failed", "failed_step": "transcribe", "transcribe_attempts": 4, "max_attempts_expected": 4, "backoff_sequence": [30, 120, 600], "downstream_calls": {"diarize": 0, "postprocess": 0, "generate": 0, "detect_sensitive": 0, "push_review": 0}}`
- `rerun_delta` = `{"preprocess": 0, "transcribe": 1, "diarize": 1, "postprocess": 1, "generate": 3, "detect_sensitive": 1, "push_review": 1}`
- `concurrent_conflict` = `True`
- `stale_reclaimed` = `1`
- `stale_error_code` = `WORKER_RESTARTED`

## 口径说明

- 用例数与通过率由 junit.xml 解析得到，未人工填写。
- 指标由 probe.py 在真实执行路径中采集，写入 outputs/metrics.json 后并入本报告。
- 存储层为 SQLAlchemy 2 模型 + Alembic 迁移；测试与演示跑 SQLite（零外部依赖），生产连接串换 postgresql+psycopg 即可。
- Redis 以进程内 FakeRedis 等价实现（SET NX EX 语义），生产替换 redis-py 命令即可。
- 退避用可注入 sleep 记录，测试断言序列为 30/120/600 秒，零等待执行。
- HTTP 接口层（POST retry / GET jobs）经 TestClient 以接口层断言覆盖。
