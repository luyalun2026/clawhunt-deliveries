# S3-TRK-011 小程序页面与漏斗日汇总表

交付两张日汇总表（`page_daily_stats` / `funnel_daily_stats`）、月活企业表、Alembic 迁移、幂等日汇总任务与测试。

## 运行

```bash
pip install -r requirements.txt
python fixtures/build_fixture.py        # 生成虚构埋点 fixtures/events.json（49 条）
python -m pytest tests -q               # 9 passed
python verify.py                        # 两遍汇总 + 幂等哈希证据 → evidence/
```

生产库：`DATABASE_URL=postgresql+psycopg://... alembic upgrade head`，模型只用通用类型（`Uuid` / `Date` / `Integer`），无方言私有类型。

## 口径

| 指标 | 定义 |
|---|---|
| `pv` | 当日该页面的 `page_view` 次数 |
| `uv` | `COUNT(DISTINCT COALESCE(contact_id, anon_id))`；同一 anon 当日先匿名后认证时，先按 anon 归并再按 contact 归并，取并集，避免同一人计两次 |
| 漏斗 | `resource_connect`：resource_view → connect_request；`event_attendance`：event_view → event_register → event_checkin（按 `event_id` 拆行）；`auth`：app_launch → auth_apply → auth_success |
| 月活企业 | 当月有**有效事件**的已认证企业去重数；有效事件 = 认证/发布/报名/签到/提问/对接，纯浏览不计 |
| 时区 | 事件 UTC 存储，切日统一转 Asia/Shanghai |

漏斗默认**不要求严格时序**（同一活动内计数即可）；设 `STRICT_FUNNEL=1` 改为逐步集合交集。

## 幂等

单日重算在一个事务内 `DELETE` 该 `(stat_date, site_id)` 再批量 `INSERT`，重跑结果逐字节一致（`evidence/verify.json` 里两次 SHA-256 相同）。

## 对接点

- 驾驶舱（S3-DASH）只读两张表；指标名与字段名见上表。
- 埋点侧只读 `track_event`，不写入；`app/analytics/track_source.py` 预留抽象，生产实现换一处注入。

## 验收对照

| 验收项 | 证据 |
|---|---|
| 三个漏斗各步人数与手算一致 | `tests/test_pipeline.py::test_funnel_counts_match_hand_calc`（期望值先手写为常量：8→3、6→4→3、9→5→2） |
| 同一人同日同页只计 1 uv | `test_uv_dedup_same_user_multiple_visits`：1 人 5 次 PV → pv=7/uv=2（含匿名转认证） |
| 重跑结果一致 | `test_rerun_idempotent` + `verify.py` 两次 SHA-256 相同 |

## 边界另测

跨日 23:59:59 / 00:00:00 归属、空日期不写行、站点隔离、严格时序模式、月活排除纯浏览企业。
