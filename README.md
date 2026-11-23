# #2288 v3 · IP 处理流水线状态机与失败重试编排（SQLAlchemy 2 + FastAPI + Alembic）

> 本版按第 2 轮返工意见整改：统一表字段与时间类型、Redis 队列 + worker（启动回收）、
> 重跑与运行共用同一把项目锁、失败步骤短路下游。交付形式为 **公开 GitHub 仓库分支（免登录 clone）**，
> 另可生成 git bundle 作离线备份。

## 一条命令跑完

```bash
python verify.py          # 内部：pytest tests -q（junitxml）→ 分组统计 → 进程内实测指标 → 报告
```

## 运行与测试方法

```bash
pip install fastapi sqlalchemy alembic httpx pytest   # 依赖
pytest tests/ -v                                      # 19 例全过
alembic upgrade head                                  # 建表 ip_project / ip_jobs
alembic downgrade base                                # 反向删除（可逆性有测试覆盖）

# 连接串用环境变量 IP_DB_URL 覆盖 alembic.ini（生产 = PostgreSQL 16）：
#   IP_DB_URL=postgresql+psycopg://user:pass@host:5432/db alembic upgrade head
```

### 最小启动示例

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import models
from pipeline import Pipeline
from app import create_app

engine = create_engine("postgresql+psycopg://user:pass@host:5432/db")  # 演示可换 sqlite:///demo.db
models.Base.metadata.create_all(engine)          # 或 alembic upgrade head
pipeline = Pipeline(sessionmaker(bind=engine, expire_on_commit=False))
app = create_app(pipeline)
```

## 本轮（v3）整改对照

| 返工意见 | 实现 | 测试 |
|---|---|---|
| 1 [major] 缺表通用字段、时间列是字符串 | `ip_project` / `ip_jobs` 主键改 **UUID**（`sa.Uuid`，PG 原生 uuid / SQLite CHAR(32)）；两表均含 `org_id`、`site_id`、`created_at`、`created_by`、`updated_at`、`deleted_at`；`started_at`/`finished_at`/审计列全部 `DateTime(timezone=True)`；迁移 `0001_initial.py` 同步且可逆 | `test_columns01`、`test_columns02`、迁移用例 |
| 2 [major] 没有队列与 worker | `worker.py`：`JobQueue`（Redis 列表 `RPUSH`/`LPOP`，进程内 `FakeRedis` 等价）+ `Worker.start()/run_once()`；`POST` 只入队并返回 202，由 worker 执行；`start()` 启动时先 `reclaim_stale()` 把 running 超 1 小时的 job 回收为 pending | `test_queue01`–`test_queue04`、回收用例 |
| 3 [major] 重跑不取同一把项目锁，可与运行中流水线并发 | `rerun_failed()` 与 `run()` 共用 `ip:lock:<project_id>`（`SET NX EX 7200`）；抢不到抛 `AlreadyRunning` → HTTP 409，且**零步骤执行** | 锁用例 4 组、重跑增量用例 |
| 4 [major] 重跑遇失败仍继续执行下游 | `rerun_failed()` 内 `failed_step` 一旦置位即 `break`，下游保持 pending 且 handler 调用计数为 0；项目置 `failed` 并记录失败步骤 | `test_stopfail01`、重试耗尽用例 |

## 实测（`outputs/verify.json`，本次运行）

- pytest：**19 passed / 0 failed**；分组：AC1 1/1、AC2 1/1、AC3 3/3、AC4 4/4、迁移与模型 2/2、边界与加固 8/8。
- happy path：10 个 job（9 succeeded + 1 skipped），6 个主步骤各执行 1 次、generate 3 个子步骤。
- 重试耗尽：transcribe 尝试 4 次（退避 30s/120s/600s），下游 5 个步骤调用计数均为 **0**。
- 重跑增量：preprocess 0 次，transcribe 及下游各 1 次（generate 3 个子步骤），`rerun_status=succeeded`。
- 并发：锁被占时 4 组用例均返回 409 且零执行；worker 启动回收 running 超 1 小时 job 为 pending。

## 结构

```
app.py                    # FastAPI：POST /jobs（入队 202）、GET /jobs、retry、rerun
models.py                 # SQLAlchemy 2 模型（UUID 主键 + 通用审计列 + DateTime(timezone=True)）
pipeline.py               # 状态机：步骤执行、重试退避、锁、reset_from、rerun_failed、reclaim_stale
worker.py                 # JobQueue（Redis 列表）+ Worker（启动回收 / 出队执行）
migrations/versions/0001_initial.py   # 可逆迁移（upgrade/downgrade）
tests/test_ip_pipeline_v2.py          # 19 例：AC1–AC4 + queue/lock/stopfail/columns/migration
verify.py / probe.py / groups.json    # 离线验证器、指标采集、分组配置
```

## 交付形式

```bash
git clone --branch 2288 https://github.com/luyalun2026/clawhunt-deliveries.git ch2288
cd ch2288 && pip install fastapi sqlalchemy alembic httpx pytest
python -m pytest tests -q        # 期望 19 passed
python verify.py                 # 期望 passed=19 failed=0
```

- 仓库分支 `2288`，本次 commit 见交付正文；`SHA256SUMS` 列全量哈希。
- 离线包：克隆后 `git bundle create 2288.bundle --all`。
- 说明：令牌无 GitHub `workflow` scope，CI 文件原样放在 `ci/workflows/`（见 `CI_NOTE.md`）。
- 全部数据虚构，不含真实企业与个人信息。
