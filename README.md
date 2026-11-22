# #2288 v2 · IP 处理流水线状态机与失败重试编排（SQLAlchemy 2 + FastAPI + Alembic）

> 本版按返工意见整改：① 交付形式改为 **公开 GitHub 仓库分支（免登录 clone，可直接复跑）**，
> 同时另附 git bundle + SHA-256 作为离线备份形式；
> ② 存储层从 sqlite3 直连改为 **SQLAlchemy 2 模型 + Alembic 迁移**；
> ③ 补齐 **HTTP 接口层**：`POST /api/ip/projects/{id}/jobs/{step}/retry` 与
> `GET /api/ip/projects/{id}/jobs`；④ 全部 4 条验收标准的测试随包交付。

## 一条命令跑完

```bash
python verify.py          # 内部：pytest tests -q（junitxml）+ python probe.py
```

## 运行与测试方法

```bash
pip install fastapi sqlalchemy alembic httpx pytest   # 依赖
pytest tests/ -v                                      # 9 例全过
alembic upgrade head                                  # 建表 ip_project / ip_jobs
alembic downgrade base                                # 反向删除（可逆性有测试覆盖）

# 连接串用环境变量 IP_DB_URL 覆盖 alembic.ini（生产 = PostgreSQL 16）：
#   IP_DB_URL=postgresql+psycopg://user:pass@host:5432/db alembic upgrade head
# 本地已实测：upgrade head → downgrade base → upgrade head 三步均成功（SQLite 与 PG 通用 DDL）
```

### 最小启动示例（生产 = PostgreSQL 16）

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

## 状态图

```
ip_jobs.status：
pending ──► running ──► succeeded            （attempt ≤ 4，退避 30s/120s/600s）
   ▲           │
   │           ├─► failed（重试耗尽）──► 项目 status=failed，failed_step 记录失败步骤
   │           └─► running 超 3600s ──► reclaim_stale 回收为 pending（WORKER_RESTARTED）
   │
   └─ generate.clips 未授权 clips ──► skipped（保持 skip，重跑不复活）

ip_project.status：pending ──► running ──► succeeded / failed
```

## 接口层

| 方法 | 路径 | 行为 |
|---|---|---|
| POST | `/api/ip/projects/{id}/jobs` | 触发整条流水线；锁冲突返回 **409** `PIPELINE_ALREADY_RUNNING` |
| POST | `/api/ip/projects/{id}/jobs/{step}/retry` | 只重跑指定步骤及下游；上游不重复执行；未知步骤 404 |
| GET | `/api/ip/projects/{id}/jobs` | 返回 ip_jobs 逐步状态（status / attempt / error_code） |

锁实现：`SET ip:lock:<project_id> <owner> NX EX 7200`。**生产替换点**：
`FakeRedis` 换成 redis-py 客户端即可（`set(key, val, nx=True, ex=7200)` / `delete(key)` 调用点无需改动）。

## 验收对照（数字由 verify.py 从 junit.xml 自动提取，见 outputs/matrix.md）

| 验收标准 | 测试 | 断言要点 |
|---|---|---|
| 1 全流程每步 succeeded/skipped | `test_ac1_happy_path_all_succeeded_or_skipped` | 全部 job ∈ {succeeded, skipped}；未授权 clips=skipped；DB 复核无其他状态 |
| 2 transcribe 连续失败 4 次 → failed | `test_ac2_retry_exhausted_four_attempts_and_backoff_sequence` | 共尝试 **4** 次；退避序列 [30,120,600]（注入 sleep 记录）；下游调用数 **0** |
| 3 retry 只重跑指定步骤及下游 | `test_ac3_retry_endpoint_reruns_only_step_and_downstream`（接口层） | preprocess 调用数不变；transcribe +1；下游各 +1 |
| 4 并发触发第二次 409 | `test_ac4_concurrent_trigger_returns_409`（接口层） | HTTP 409 + `PIPELINE_ALREADY_RUNNING`；编排器直调抛 AlreadyRunning |

另附：Alembic 迁移可逆性（upgrade head → downgrade base）、失败修复重跑、未知步骤 404、锁释放后可再触发。

## 目录

```
models.py                  # SQLAlchemy 2 模型（ip_project / ip_jobs）
pipeline.py                # 编排器：状态机 + 重试 + 重跑 + stale 回收（SQLAlchemy 会话版）
app.py                     # FastAPI 接口层（触发 / retry / jobs）
migrations/versions/0001_initial.py   # 可逆迁移
alembic.ini                # 迁移配置（测试里 programmatic 覆盖 sqlalchemy.url）
probe.py / verify.py / groups.json    # 实测与自动报告
tests/test_ip_pipeline_v2.py          # 9 例
```

## 复跑四步（推荐：公开仓库，无需登录）

```bash
git clone --branch 2288 https://github.com/luyalun2026/clawhunt-deliveries.git repo
cd repo
pip install fastapi sqlalchemy alembic httpx pytest
pytest tests/ -v              # 期望 9 passed
```

离线备用形式（git bundle，同样可复跑）：

```bash
curl -LO "https://clawhunt-relay.app.workbuddy.host/2288/pkg.bundle?sharecode=R24KOKETNU"
sha256sum pkg.bundle          # 与交付正文给出的 SHA-256 对照
git clone pkg.bundle repo && cd repo && pytest tests/ -v
```

> 说明：`ci/workflows/` 下的工作流文件原始路径为 `.github/workflows/`，
> 因推送所用令牌无 workflow 权限而改放此处，见 `CI_NOTE.md`；本地 `pytest tests -q` 与 CI 等价。
