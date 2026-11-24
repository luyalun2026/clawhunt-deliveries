# S6-POD-041 节目对接请求与相关推荐转化归因

交付归因引擎（直连 + 辅助）、`episode_conversion_stats` 日汇总任务、模型与测试。

## 运行

```bash
pip install -r requirements.txt
python -m pytest tests -q      # 13 passed
```

日汇总：`run_day(session, stat_date, org_id=..., site_id=..., clicks=[...], conversions=[...], intro_requests=[...], episodes=[...])`；回补用 `run_range(session, start, end, ...)`。生产侧把 `clicks/conversions/intro_requests` 换成真实查询与接口桩（`stubs.py` 语义）即可，汇总逻辑不变。

## 归因规则

**直连归因**：`podcast_intro_requests` 本身带 `episode_id`，按 `episode_id + 创建日` 聚合三态：`submitted ⊇ staff_approved ⊇ accepted`（累计漏斗）。脏数据（accepted 但无 approved）按漏斗规则自动上卷到 approved，不产生 accepted > approved。

**辅助归因**：
1. 窗口 `[clicked_at, clicked_at + 24h]`，**闭区间**：24h00m00s 计入，24h00m01s 不计。
2. 匹配键 `(user_id, item_type, item_id)`；点击与转化必须同用户、同对象。
3. 多期竞争：同一转化命中多条点击时，**归最近一次点击的那一期**；被淘汰的点击不计数。
4. 去重：相同 `click_id`（或同四元组）重复上报只算一次，记 warning。
5. 跨月：统计日按**点击日**（Asia/Shanghai）归属，避免月末回补漏数。

**输出**：`episode_conversion_stats(episode_id, stat_date, intro_requests, intro_staff_approved, intro_accepted, assisted_event_signups, assisted_course_signups, assisted_opportunity_requests)`，唯一键 `(episode_id, stat_date)`；无数据的节目也输出 0 行，不停更。

## 幂等

单日重算先 `DELETE` 该 `(stat_date, site_id)` 再插入，重跑结果完全一致（`test_run_day_and_rerun_idempotent`）。

## 验收对照

| 验收项 | 证据 |
|---|---|
| 25h 不计、23h 计入 | `test_window_23h_counted_25h_excluded`：23h/24h 计 2 条，25h 排除；秒级边界另测 24h00m00s vs 24h00m01s |
| 两期点同一活动只归最近一期 | `test_competing_clicks_attributed_to_latest`（EP1→EP2，仅 EP2 +1）；另有「最近点击超窗则回退更早点击」用例 |
| 引荐三计数与源表一致 | `test_intro_counts_match_source_table`：与源表 `Counter` 分组逐期对拍，差集为空 |

## 边界另测

跨月归点击日、关闭个性化推荐无点击时辅助列为 0、event 与 course 分别计数、重复点击去重、无数据节目输出 0 行、accepted 但未 approved 的脏数据上卷。
