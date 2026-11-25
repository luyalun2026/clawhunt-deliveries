# S4-E2E-026 · 闭环四：小程序行为回流后的会员画像与月活核对（交付页）

pytest + httpx 全绿；互动卡片截图由 headless 浏览器实拍，6 项计数可见。

## 运行方法

```bash
python seed.py --scenario loop4     # 构造场景数据（幂等，自动重置）
python -m pytest tests/ -q          # 9 例：AC1–AC4 + 5 个边界用例
python screenshot_card.py           # 生成 card.html + screenshots/interaction_card.png
```

## 有效互动定义（AC4 口径，与 `loop4_common.INTERACTION_TYPES` 同源）

**认证、发布需求、报名、签到、提问**（不含纯浏览 browse）。
月活跃会员企业 = 当月有 ≥1 条有效互动会员的企业；分子 = 此类企业数，分母 = 在册企业数。
软删除会员的互动不计；跨月互动不计当月；重复签到（同会员同活动）按唯一约束去重计 1。

## 验收标准对应

| # | 验收标准 | 结果 | 证据 |
|---|---|---|---|
| 1 | 6 项计数与构造数据一致 | ✅ 认证1/需求1/报名2/签到1/提问3/转人工1，期望值与 seed 同源（`loop4_common.EXPECTED_COUNTS`） | `artifacts/pytest.txt` |
| 2 | 只浏览对照企业不计月活 | ✅ 分子含 ent-A-0001、不含 ent-B-0002 | `artifacts/pytest.txt` |
| 3 | 卡片截图可见 6 项计数 | ✅ `screenshots/interaction_card.png`；生成脚本内断言 HTML 六项计数文本与实跑结果逐项一致后才落盘 | `artifacts/card_data.json` |

## 场景数据（seed.py 单一来源）

- 企业 A：会员 U1 —— 认证 1、需求 1、报名 2 场（签到 1 场）、提问 3（转人工 1）；
- 企业 B：会员 U2 只浏览（对照，不计月活）；
- 边界数据：U1 纯浏览 1 条、上月需求 1 条、软删除会员互动 1 条、U1 重复签到 1 条（被去重）。

## 边界用例（tests 内）

重复签到去重 · 跨月不计 · 软删除会员不计 · 无 token 401（画像与驾驶舱接口）· 空数据集计数全 0、占比 0。

## 桩与对接点

`stub_app.py` 按 S2-CRM / S3-DASH / S3-TRK 契约先行提供
`GET /api/crm/members/{id}/portrait`、`GET /api/dash/mau`、`GET /api/track/interactions`
（Bearer 鉴权，SQLite 持久化，生产替换仅改 base_url 与数据库连接串，PG16 对接点即 SQLAlchemy/psycopg 常规替换）。
