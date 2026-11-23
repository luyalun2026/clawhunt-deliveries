# 运行报告（自动生成）

- 生成时间：2026-11-23T23:00:10
- 命令：`python verify.py`（内部 `pytest tests -q` + `python probe.py`）
- pytest 汇总：`19 passed, 1 warning in 2.61s`；退出码 0
- 用例 19，通过 19，失败 0

## 用例 × 结果矩阵

| 验收分组 | 用例数 | 通过 | 失败 | 结论 |
|---|---|---|---|---|
| AC1 全流程步骤成功或跳过 | 1 | 1 | 0 | 通过 |
| AC2 重试耗尽置 failed | 1 | 1 | 0 | 通过 |
| AC3 重跑只跑指定步骤及下游 | 3 | 3 | 0 | 通过 |
| AC4 队列化触发：入队即返回 / worker 执行 / 并发锁 409 | 8 | 8 | 0 | 通过 |
| AC5 重跑失败即停（下游保持 pending 不被调用） | 2 | 2 | 0 | 通过 |
| 统一列约定（UUID 主键 / org_id / site_id / 审计列 / 时间类型） | 3 | 3 | 0 | 通过 |
| 迁移与模型（SQLAlchemy 2 / Alembic） | 1 | 1 | 0 | 通过 |
| **合计** | **19** | **19** | **0** | **全部通过** |

## 实测指标（probe.py 运行期提取）

- `happy_path` = `{"status": "succeeded", "total_jobs": 10, "succeeded": 9, "skipped": 1, "step_calls": {"preprocess": 1, "transcribe": 1, "diarize": 1, "postprocess": 1, "detect_sensitive": 1, "push_review": 1, "generate": 3}, "job_statuses": ["skipped", "succeeded"]}`
- `retry_exhausted` = `{"status": "failed", "failed_step": "transcribe", "transcribe_attempts": 4, "max_attempts_expected": 4, "backoff_sequence": [30, 120, 600], "downstream_calls": {"diarize": 0, "postprocess": 0, "generate": 0, "detect_sensitive": 0, "push_review": 0}}`
- `rerun_delta` = `{"preprocess": 0, "transcribe": 1, "diarize": 1, "postprocess": 1, "generate": 3, "detect_sensitive": 1, "push_review": 1}`
- `rerun_status` = `succeeded`
- `stop_on_failure` = `{"status": "failed", "failed_step": "diarize", "downstream_delta": {"postprocess": 0, "generate": 0, "detect_sensitive": 0, "push_review": 0}}`
- `lock_conflicts` = `{"run": true, "rerun": true}`
- `stale_reclaimed` = `1`
- `stale_error_code` = `WORKER_RESTARTED`
- `queue_worker` = `{"depth_after_enqueue": 1, "handled_called_before_worker": 0, "worker_outcome_status": "succeeded", "handled_calls_after_worker": 9, "depth_after_worker": 0}`
- `schema_convention` = `{"job_pk_type": "CHAR(32)", "project_pk_type": "CHAR(32)", "started_at_type": "DATETIME", "common_columns_present": true}`

## 口径说明

- 用例数与通过率由 junit.xml 解析得到，未人工填写。
- 指标由 probe.py 在真实执行路径中采集，写入 outputs/metrics.json 后并入本报告。
- v3 整改（对应第 2 轮返工 5 条）：POST 入队即返回由 worker 执行；worker 启动执行 reclaim_stale（running>1h 回收 pending）；retry 与 run 取同一把 ip:lock:<project_id>（SET NX EX 7200），锁被占 409；重跑失败即停、下游保持 pending；两表统一 UUID 主键 + org_id/site_id + created_at/created_by/updated_at/deleted_at，时间列 DateTime(timezone=True)。
- 存储层为 SQLAlchemy 2 模型 + Alembic 迁移；测试与演示跑 SQLite（零外部依赖），生产连接串换 postgresql+psycopg 即可（Uuid 类型 PG 上为原生 uuid 列）。
- Redis 以进程内 FakeRedis 等价实现（SET NX EX / RPUSH / LPOP 语义），生产替换 redis-py 同名命令即可；队列与 worker 见 worker.py。
- 退避用可注入 sleep 记录，测试断言序列为 30/120/600 秒，零等待执行。
- 接口说明只写已实现且有测试覆盖的行为（POST /jobs 入队 202、retry 加锁 409、GET jobs、POST /api/ip/worker/tick）。
