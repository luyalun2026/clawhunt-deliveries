# S5-GW-027 会员空间平台 · 草稿入队内部接口、幂等去重与生效事件外发表

内部服务：为其他模块提供「AI 草稿入队 → 幂等去重 → 生效/驳回/过期 → outbox 事件外发 → 生效内容读取」的完整链路。本接口与事件只提供内容，不提供任何对外发送通道。

## 运行方法

```bash
pip install -r requirements.txt
uvicorn app.main:app --port 8154
```

环境变量（均只从环境变量读取）：

| 变量 | 说明 | 默认 |
| --- | --- | --- |
| `DATABASE_URL` | SQLAlchemy 连接串（PostgreSQL 16 生产 / SQLite 本地） | `sqlite:///./ch2154.db` |
| `REVIEW_SERVICE_KEYS` | 服务凭证，逗号分隔 | `svc-test-key` |
| `DRAFT_EVENT_SUBSCRIBER_URL` | 订阅方 webhook 地址 | 空（投递任务跳过） |
| `DELIVERY_BATCH_SIZE` | 投递任务单轮最大事件数 | 100 |

## 测试方法

```bash
pip install -r requirements.txt
python -m pytest tests -q
```

当前结果：**12 passed**（覆盖验收标准 AC1–AC4，另有鉴权、级别降级、终态不可重迁移、投递至少一次与失败重试等测试）。

## API

所有内部接口均需请求头 `X-Service-Key: <REVIEW_SERVICE_KEYS 之一>`。

### POST /api/review/drafts（内部入队）

入参：`feature_code, source_type, source_id, title, ai_content, schema_id, schema_version, gw_request_id, drafter_id, requested_level(strict|standard|draft)`（可选 `org_id/site_id`）。

- 入队前按登记 schema 校验 `ai_content`，不合格返回 **422** 且不落库；
- 同一 `gw_request_id` 重复提交返回**已有草稿**（幂等，两次响应 `draft_id` 相同）；新建返回 201，幂等命中返回 200；
- 最终级别由状态机规则决定并随响应返回：`confidence_score` ≥ `requested_level` 门槛（strict 0.80 / standard 0.60 / draft 0.40）→ 保留 requested 级别，否则降一级（L3→L2→L1）。

### POST /api/review/drafts/{id}/transition

`{"action": "effective" | "rejected" | "expired"}`。草稿状态变更与 outbox 表 `ai_draft_events` 写入在**同一事务**内提交（AC3 有事务回滚测试）。终态不可重复迁移（409）。

### GET /api/review/drafts/{id}/effective-content

仅 `effective` 状态返回生效内容；非 effective（或草稿不存在）返回 **409**。

## outbox 与投递任务（至少一次）

- 迁移：`alembic upgrade head`（`alembic/versions/0001_init.py` 建 `ai_drafts` 与 `ai_draft_events`）；测试与本地开发由 `Base.metadata.create_all` 自动建表。
- `app/delivery.py` 轮询 `delivered_at IS NULL` 的事件，POST 到 `DRAFT_EVENT_SUBSCRIBER_URL`；**订阅方 2xx 才标记 `delivered_at`**，失败保留并在下轮重试（at-least-once）。

```bash
python -m app.delivery --once          # 投递一轮
python -m app.delivery --interval 30   # 常驻轮询
```

## 订阅方对接说明

1. 在 `DRAFT_EVENT_SUBSCRIBER_URL` 提供 webhook，接收 POST JSON：
   `{event_id, event_type, draft_id, feature_code, source_type, source_id, payload}`；
2. `event_type` ∈ `ai.draft.effective / ai.draft.rejected / ai.draft.expired`；
3. 投递为**至少一次**：请以 `draft_id`（或 `event_id`）做幂等去重；
4. 订阅方仅接收事件通知，业务模块读取生效内容应调 `GET /api/review/drafts/{id}/effective-content`。

## 依赖与对接点（本单依赖=无）

- schema 校验器内置注册表（`app/validator.py`，`member_space.chat_summary@1.0`、`member_space.resource_match@1.0`）；生产环境 schema 管理服务就绪后替换注册来源即可，接口不变。
- 状态迁移入口 `POST /transition` 目前供集成方在联调期驱动状态机；对接「AI 复核队列」工单后由复核队列回调驱动。
