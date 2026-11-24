# 执行环境与问题单

## 一、执行环境（本轮 12 个场景与 5+5 汇总 SQL 的真实运行环境）

- 数据库：**PostgreSQL 16.4**（`SELECT current_setting('server_version')` 实测值）
- 连接方式：`DATABASE_URL=postgresql://...`；`tools/run_sql.py` 与 `tools/run_matrix.py` 均通过该连接串取连接
- 建库脚本：`sql/00_schema.sql`（15 张表 + 5 个索引）→ `sql/01_seed.sql`（虚构数据）→ `sql/00_api_pg.sql`（10 个接口桩函数）
- 表结构要点：`site` / `enterprise` / `enterprise_site` / `event` / `opportunity` / `sop_task` / `contact` /
  `contact_owner_history` / `knowledge_article` / `dict_entry` / `site_config` / `group_config` /
  `event_registration` / `referral` / `scenario_result`
- 接口桩（PL/pgSQL，全部读写真实表，无内存模型）：`api_change_contact_owner`、`api_transfer_opportunity`、
  `api_register_event`、`api_read_kb`、`api_upsert_site_dict`、`api_dict_entries`、`api_config`、
  `api_visible_contacts`、`api_read_opportunity_as_site`、`api_assert_site_writable`
- 隔离方式：每个场景在独立事务中执行，读完 `scenario_result` 立即 ROLLBACK（`test_18` 断言场景间无残留）
- 数据性质：全部为虚构数据（会所 S1/S2/S3/S9、企业 E01–E23/E90），不含任何真实企业或个人信息

## 二、12 个场景的执行结果

| 场景 | 是否一致 | 实际结果 |
|---|---|---|
| S01 同一会员企业同时入驻两个会所 | 一致 | 企业记录 1 条；有效在驻关系 2 条（S1,S2）；未过滤原始关系 3 条 |
| S02 会员在 B 会所报名 A 会所公开活动 | 一致 | 报名 host=S1 member=S2 ent=E01 落库 1 行；私有活动被拒=True(HTTP_403 event V18 not visible to S2) |
| S03 联系人跨会所更换负责人 | 一致 | history=1 条；contact.site=S2 owner=owner-s2-b2；S2 可见=1 S1 可见=0 |
| S04 会所停业后历史数据只读 | 一致 | 读=2 行；写被拒=True(HTTP_409 site S2 closed: read-only)；ct-2 负责人仍为 owner-s2-b1 |
| S05 商机从 A 会所转介到 B 会所 | 一致 | site=S2 转介=1 条(from=S1)；A 视角字段={ent_name,id,stage}；B 视角字段={amount_cent,ent_id,ent_name,id,owner_id,stage} 金额=1200000 |
| S06 知识库「机构共享」文章 | 一致 | S2 命中 1 行、S3 命中 1 行；标题=机构统一服务标准 scope=org |
| S07 知识库「会所私有」文章 | 一致 | 本会所=1 行；跨会所=0 行；不存在=0 行 |
| S08 机构级字典（空间类型） | 一致 | 覆写被拒=True(HTTP_409 cannot override org dictionary key office)；S2 字典 3 项；coworking 生效=1 |
| S09 会所级配置（价格规则） | 一致 | S1 保证金比例=2000；S2=3000；S3 最短租期=6 |
| S10 总部跨会所汇总 | 一致 | 在驻企业 23/23(朴素26)；活动 11/11(朴素15)；签约 6/6(朴素7)；SOP 完成率 0.7500/0.7500(朴素0.6818)；空置工位 21/21(朴素50) |
| S11 软删除语义 | 一致 | 列表命中=0；物理记录=1 条 deleted_at=2026-11-20 10:00:00 |
| S12 数据导出范围 | 一致 | 导出行=2（应为 2）；越界行=0；明细=ct-1,ct-3 |

## 三、问题单
本轮 12 个场景实际结果与期望行为一致，无待修问题（0 条）。
