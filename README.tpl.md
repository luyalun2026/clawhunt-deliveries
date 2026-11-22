# #2288 IP 处理流水线状态机与失败重试编排

个人 IP 内容助手的处理流水线：7 个有序步骤（`preprocess → transcribe → diarize → postprocess → generate(4 子步骤) → detect_sensitive → push_review`），每步独立记录 `status / attempt / started_at / finished_at / error_code`，失败按 30s / 2min / 10min 退避重试 3 次，重跑只跑指定步骤及其下游。

## 一条命令跑完

```bash
python verify.py          # 内部：pytest tests -q  +  python probe.py
```

本次实测：`{{SUMMARY}}`，用例 {{TOTAL}} 条，通过 {{PASSED}}，失败 {{FAILED}}（生成于 {{GEN_AT}}）。

## 验收对照

{{MATRIX}}

## 实测指标（运行期提取，非手写）

{{METRICS}}

## 四条验收标准的实现路径

**1. 桩函数跑完整条流水线，每步 succeeded 或 skipped**
`Pipeline.run` 按序执行，前置全部为终态才进入下一步；`generate` 的 4 个子步骤（章节 / 节目介绍 / 金句 / 切片）互不阻塞，其中一个失败不阻止其余落库。`scopes.clips == False` 时切片子步骤直接置 `skipped` 且不调用实现（`test_02` 断言 generate 只被调用 3 次）。

**2. transcribe 连续失败共尝试 4 次，项目 failed**
`_run_step` 循环 `1..4`：第 1 次 + 3 次重试，退避序列 `30/120/600` 秒（`test_05` 断言 `sleeps == [30, 120, 600]`，零等待执行）。第 4 次失败落 `attempt=4`、`error_code=TRANSCRIBE_FAILED`，项目 `failed`、`failed_step=transcribe`，下游调用计数为 0。

**3. 重跑只跑指定步骤及下游**
`reset_from` 把目标步骤与下游置回 `pending`，上游保持终态；`rerun_failed` 只执行这些步骤。`test_08` 断言 preprocess/transcribe/diarize/postprocess 调用增量为 0，`test_09` 验证从 diarize 重跑时上游不重复。

**4. 同一项目并发触发两次，第二次 409**
Redis 锁 `ip:lock:{project_id}`（`SET NX EX 7200`）在 `run` 入口获取、`finally` 释放；拿不到抛 `AlreadyRunning`，接口层映射 409 `PIPELINE_ALREADY_RUNNING`。`test_11` 用两线程并发，断言结果恰好为一个成功 + 一个 409。

## worker 重启与锁过期

- `reclaim_stale()`：`status=running` 且 `started_at` 早于 1 小时的任务置回 `pending`，`error_code=WORKER_RESTARTED`；`succeeded/skipped` 不受影响（`test_12`/`test_13`）。
- 锁 TTL 7200 秒，过期后可重入（`test_14`）。

## 目录结构

```
ip_pipeline.py           DDL / FakeRedis / 编排器 / 重跑 / 回收 / 进度
probe.py                 整链调用次数、重试耗尽、重跑增量、锁与回收实测
tests/test_ip_pipeline.py {{TOTAL}} 条用例
verify.py / groups.json / outputs/
```

## 接入生产的两处替换

| 本包实现 | 生产替换 |
|---|---|
| `FakeRedis`（进程内、带 NX/EX） | `redis.Redis.set(key, val, nx=True, ex=7200)`，语义一致 |
| 注入的 handler 桩 | 真实 ASR / 说话人分离 / LLM 生成实现，签名 `handler(sub_step) -> None` |

## 边界与不做的事

- 不实现多项目队列调度（worker 拉取逻辑另一单），本包只保证单项目串行语义。
- 不做切片文件 CDN 分发与前端进度页。
- generate 的 4 个子步骤并发度由调用方决定，本包只保证互不阻塞与状态独立。
