# S6-POD-040 · 收听数据日汇总任务：播放、听众、完播率与留存分段

> 会员空间平台 · Stage vi 数据链路 · podcast 汇总
> SQLAlchemy 2 模型 + Alembic 迁移 + 独立双实现对账 + pytest 10 用例全过

## 一、验收标准逐条对应

| # | 验收标准 | 实现 | 证据 |
|---|---|---|---|
| 1 | 夹具数据的汇总结果与口径文档中手算的期望值逐项一致 | 夹具 2753 条事件（seed=20261127，3 期节目×7 天，≥2000 条）；期望值由**独立实现** `tools/calc_expected.py` 朴素字典遍历手算 → `outputs/expected.json`，测试对 episode/column/all 三层逐字段断言 | `test_ac1_fixture_vs_expected_per_field` ✅、`test_ac1_column_and_all_rows_match` ✅ |
| 2 | 对同一日期连续运行两次，汇总表行数与数值不变 | 每日期单事务先删后插；测试以业务键（stat_date/episode_id/column_id/org）排序取内容哈希（排除 uuid 主键与时间戳），两次运行哈希相等 | `test_ac2_idempotent_same_day_twice` ✅、`test_ac2_single_day_twice_rowcount_unchanged` ✅ |
| 3 | --from --to 回补 7 天后，每天各有一行全站汇总 | `run(from, to)` 区间回补；全站行 `episode_id='__ALL__'` 每天恰 1 行；单日回补只动该日其他日数值不变；to<from 拒绝 | `test_ac3_backfill_7_days_one_all_row_per_day` ✅、`test_ac3_backfill_single_day_touches_only_that_day` ✅ |

补充边界：0 听众 completion_rate NULL、缺时长节目 avg_listen_ratio NULL、进度恰好 100% 计入 reach_100、未知 source 原样保留、跨午夜 session 按事件时间戳归属。

## 二、运行方法

```bash
pip install pytest sqlalchemy
python tools/gen_fixture.py                                   # 生成夹具库（2753 条）
python tools/calc_expected.py                                 # 独立手算期望值
python -m app.aggregate --from 2026-11-01 --to 2026-11-08 \
       --db sqlite:///podcast_fixture.db                      # 汇总任务
python -m pytest tests/ -v                                    # 10 passed
```

生产环境：`--db postgresql+psycopg://...`（JSONB/UUID 方言自动切换）；迁移：
`alembic upgrade head`（`migrations/versions/0001_pod040_init.py`，可逆）。

## 三、交付物

- `app/models.py` — SQLAlchemy 2 模型（episodes / listening_events / episode_daily_stats / column_daily_stats，统一 org_id/site_id/created_at/created_by/updated_at/deleted_at 软删除字段）
- `app/aggregate.py` — 汇总任务核心 + CLI（时区 Asia/Shanghai；每日期单事务先删后插）
- `migrations/versions/0001_pod040_init.py` — Alembic 迁移（upgrade/downgrade 可逆）
- `docs/口径文档.md` — 指标口径（与实现同义、与测试对账对应）
- `tools/gen_fixture.py` / `tools/calc_expected.py` — 夹具与独立期望值计算
- `outputs/expected.json` — 手算期望值；`outputs/pytest_main.txt` — 测试输出
- `tests/test_aggregate.py` — 10 用例

### 口径要点（详见 docs/口径文档.md）
- unique_listeners：user_id 优先 / anon_id 兜底，episode_view 不计听众。
- 全站行（__ALL__）plays/listeners/completes 跨节目去重；reach 按听众跨节目最大进度。
- completion_rate 分母 0 → NULL；缺时长节目 avg_listen_ratio → NULL；全站 avg 恒 NULL。

## 四、测试结果

`outputs/pytest_main.txt`：10 passed / 0 failed；`outputs/verify.json` 数字由 pytest 输出自动提取（零手写）；`SHA256SUMS` 全部文件哈希。
