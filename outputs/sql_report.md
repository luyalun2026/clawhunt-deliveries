# 5 个汇总查询 SQL 与对拍结果（由 tools/run_sql.py 自动生成）

- 执行引擎：**postgresql**（SQL 为 PostgreSQL 方言；无 PG 服务时由 SQLite 3 执行同一批 SQL）
- 有效会所（site.deleted_at IS NULL）：S1, S2, S3
- 月份参数：2026-11

## 在驻企业数（site_member_count）

- 总部汇总 SQL（`sql/10_agg_member_count.sql`）：**23**
- 各会所单独 SQL 之和（3 个会所）：**23**
- 分会所明细：S1=6、S2=5、S3=12
- 未加过滤条件的朴素计数：26（与汇总值不同 → 过滤条件真实生效，断言非恒等式）
- 对拍结论：PASS（diff=0）

## 月度活动场次(2026-11)（monthly_event_count）

- 总部汇总 SQL（`sql/11_agg_monthly_events.sql`）：**11**
- 各会所单独 SQL 之和（3 个会所）：**11**
- 分会所明细：S1=6、S2=3、S3=2
- 未加过滤条件的朴素计数：15（与汇总值不同 → 过滤条件真实生效，断言非恒等式）
- 对拍结论：PASS（diff=0）

## 商机转化数（opportunity_conversion）

- 总部汇总 SQL（`sql/12_agg_opportunity_signed.sql`）：**6**
- 各会所单独 SQL 之和（3 个会所）：**6**
- 分会所明细：S1=3、S2=2、S3=1
- 未加过滤条件的朴素计数：7（与汇总值不同 → 过滤条件真实生效，断言非恒等式）
- 对拍结论：PASS（diff=0）

## SOP 完成率（sop_completion_rate）

- 总部汇总 SQL（`sql/13_agg_sop_rate.sql`）：**0.75**
- 各会所单独 SQL 之和（3 个会所）：**0.75**
- 分子/分母：汇总 15/20，分会所求和 15/20
- 分会所明细：S1 8/10、S2 3/6、S3 4/4
- 未加过滤条件的朴素分子/分母：15/22（与汇总 15/20 不同 → 过滤条件真实生效，断言非恒等式）
- 对拍结论：PASS（diff=0.0）

## 空置工位数（vacant_seat_count）

- 总部汇总 SQL（`sql/14_agg_vacant_seats.sql`）：**21**
- 各会所单独 SQL 之和（3 个会所）：**21**
- 分会所明细：S1=14、S2=7、S3=0
- 未加过滤条件的朴素计数：28（与汇总值不同 → 过滤条件真实生效，断言非恒等式）
- 对拍结论：PASS（diff=0）

## 汇总

- 5 项指标对拍：全部通过；pass=5/5；filters_effective=5/5
- 引擎：postgresql；SQL 文件：建库 3 份（00_schema / 01_seed / 00_api_pg）+ 查询 10 条（5 汇总 + 5 按会所）+ 场景脚本 12 份（sql/scenarios/S01~S12）
