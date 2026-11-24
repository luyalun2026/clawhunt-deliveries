# 12 个场景执行矩阵（由 tools/run_matrix.py 在 PostgreSQL 16.4 上自动生成）

- 执行引擎：**PostgreSQL 16.4**（本单【统一技术约定】要求的版本）
- 建库脚本：`sql/00_schema.sql`（表结构）→ `sql/01_seed.sql`（虚构数据）→ `sql/00_api_pg.sql`（接口桩函数）
- 每个场景一份 `sql/scenarios/Sxx.sql`，脚本内为真实 SQL / 接口桩调用，
  最后一行把「期望 / 实际 / 是否通过」写入 `scenario_result` 表；本矩阵由 `outputs/scenarios.json` 渲染，未手写任何数字。
- 场景之间用事务隔离：每个场景执行后立即 ROLLBACK，互不污染。

| 场景 | 期望行为 | 执行脚本 | 实际结果 | 结论 |
|---|---|---|---|---|
| S01 同一会员企业同时入驻两个会所 | CRM 中只有一条企业记录，有效入驻关系为两条（S1/S2 各一条；软删会所 S9 的关系不计） | `sql/scenarios/S01.sql` | 企业记录 1 条；有效在驻关系 2 条（S1,S2）；未过滤原始关系 3 条 | 一致 |
| S02 会员在 B 会所报名 A 会所公开活动 | 公开活动允许跨会所报名，报名记录带 host_site=S1 与 member_site=S2；私有活动跨会所必须 403 | `sql/scenarios/S02.sql` | 报名 host=S1 member=S2 ent=E01 落库 1 行；私有活动被拒=True(HTTP_403 event V18 not visible to S2) | 一致 |
| S03 联系人跨会所更换负责人 | 联系人由 S1 迁至 S2 并换负责人：历史留 1 条；变更后 S2 可见、S1 不可见 | `sql/scenarios/S03.sql` | history=1 条；contact.site=S2 owner=owner-s2-b2；S2 可见=1 S1 可见=0 | 一致 |
| S04 会所停业后历史数据只读 | 停业会所读接口正常返回历史数据，写接口 409 且数据未被改动 | `sql/scenarios/S04.sql` | 读=2 行；写被拒=True(HTTP_409 site S2 closed: read-only)；ct-2 负责人仍为 owner-s2-b1 | 一致 |
| S05 商机从 A 会所转介到 B 会所 | site_id 改为 S2 + 转介记录 1 条；A 会所仅见脱敏摘要（无 amount_cent / ent_id），B 会所见完整字段 | `sql/scenarios/S05.sql` | site=S2 转介=1 条(from=S1)；A 视角字段={ent_name,id,stage}；B 视角字段={amount_cent,ent_id,ent_name,id,owner_id,stage} 金额=1200000 | 一致 |
| S06 知识库「机构共享」文章 | 机构共享（scope=org）文章在任何有效会所均可读到 | `sql/scenarios/S06.sql` | S2 命中 1 行、S3 命中 1 行；标题=机构统一服务标准 scope=org | 一致 |
| S07 知识库「会所私有」文章 | 会所私有文章仅本会所可读；跨会所与不存在均 0 行（404 语义一致） | `sql/scenarios/S07.sql` | 本会所=1 行；跨会所=0 行；不存在=0 行 | 一致 |
| S08 机构级字典（空间类型） | 覆写机构键被 409 拒绝；会所新增键生效（S2 视角 3 个空间类型） | `sql/scenarios/S08.sql` | 覆写被拒=True(HTTP_409 cannot override org dictionary key office)；S2 字典 3 项；coworking 生效=1 | 一致 |
| S09 会所级配置（价格规则） | 会所专属配置优先（S1=2000），无专属则回落集团通用（S2=3000），非价格键同样回落（S3 租期=6） | `sql/scenarios/S09.sql` | S1 保证金比例=2000；S2=3000；S3 最短租期=6 | 一致 |
| S10 总部跨会所汇总 | 5 项指标总部汇总值 = 各会所单独查询之和，且去掉过滤条件后数值会变（非恒等式） | `sql/scenarios/S10.sql` | 在驻企业 23/23(朴素26)；活动 11/11(朴素15)；签约 6/6(朴素7)；SOP 完成率 0.7500/0.7500(朴素0.6818)；空置工位 21/21(朴素50) | 一致 |
| S11 软删除语义 | 软删后不出现在任何列表/导出，但物理记录保留（deleted_at 有值） | `sql/scenarios/S11.sql` | 列表命中=0；物理记录=1 条 deleted_at=2026-11-20 10:00:00 | 一致 |
| S12 数据导出范围 | 导出行严格等于本会所可见范围（含被软删记录已剔除），不含跨会所行 | `sql/scenarios/S12.sql` | 导出行=2（应为 2）；越界行=0；明细=ct-1,ct-3 | 一致 |


## 脚本哈希（sha256）

| 场景 | 脚本 | sha256 |
|---|---|---|
| S01 | `sql/scenarios/S01.sql` | `01d20c7217c936b20e356c41b5a6a006cec9307585f5640d8dc844e6188d4e08` |
| S02 | `sql/scenarios/S02.sql` | `1e1291b8c9dbdf26a1816323e6da86f19b27cfc015acaa07ad7e976a0b9ae86d` |
| S03 | `sql/scenarios/S03.sql` | `2fc7d7d601f7d6eac2c7fc9dc65cc0728a9e957c13c27683ef7962a2736b9d86` |
| S04 | `sql/scenarios/S04.sql` | `755a7006c707182a25d550c02bdf1927745a4623fe6cce10a927f3eca0c7ff53` |
| S05 | `sql/scenarios/S05.sql` | `ccfe4c12d7383bef4505fdd30c891f842018afc7c7d9b0a9a32a2fd92dbb411e` |
| S06 | `sql/scenarios/S06.sql` | `95d992588bdd08020d5ba373597417cc482c5b8bb9b45d5cbecbd46a64c0ed5b` |
| S07 | `sql/scenarios/S07.sql` | `9ed5bde84d46d477e8b1eadd9bccc037d08226b1ffca63fe2940ca826440a5be` |
| S08 | `sql/scenarios/S08.sql` | `f3af3e00c844fc12be3caceb9e52a383a3c68bec01ec7e3960a087db0bd43553` |
| S09 | `sql/scenarios/S09.sql` | `133e4fbcd10521acfc36db4e4039245944bd09015224c2b63214fbc43386e0ee` |
| S10 | `sql/scenarios/S10.sql` | `f95e45a8f644a2b73a1de1185b48949b32d36eb8b71eb36b3d9cf4ae07cb2c73` |
| S11 | `sql/scenarios/S11.sql` | `2e0d0c63d840bb7d336f20cf503d29e7beb799ff93207416310ae3555e68e5f2` |
| S12 | `sql/scenarios/S12.sql` | `a63d63a8808b7547c20791e77e882c0953a53f226dda686be37a353f8529dc3f` |

## 汇总

- 场景数：12；通过：12；不一致：0

