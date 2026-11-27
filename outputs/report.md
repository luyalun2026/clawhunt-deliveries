# 多会所字段覆盖扫描报告（schema=main）

业务表总数：7（与 information_schema 统计一致）
级别统计：blocker=2 major=3 warn=0

| 表名 | 分类 | 缺失字段 | 缺失索引 | 跨 org 引用风险 | 问题级别 |
|---|---|---|---|---|---|
| fake_room | site | site_id | (org_id) 或 (org_id, site_id) 前缀索引 | - | blocker |
| sneaky_table | unregistered | - | - | - | blocker |
| venue | site | - | (org_id) 或 (org_id, site_id) 前缀索引; (site_id) 索引 | - | major |
| fake_venue | site | - | (org_id) 或 (org_id, site_id) 前缀索引; (site_id) 索引 | - | major |
| contact | org | - | (org_id) 或 (org_id, site_id) 前缀索引 | - | major |
| member_company | org | - | - | - | ok |
| region_code | global | - | - | - | ok |