-- #1964 PostgreSQL 16 专属对象（SQLite 测试路径不执行）。
-- EXCLUDE USING gist：同名规则表的 published 版本生效区间互斥（半开区间 [)）。
CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE quote_rule_set ADD CONSTRAINT no_overlap_published_rule_set
  EXCLUDE USING gist (
    org_id WITH =,
    name WITH =,
    daterange(valid_from, COALESCE(valid_until, 'infinity'::date), '[)') WITH &&
  )
  WHERE (status = 'published' AND deleted_at IS NULL);

-- 复现：
--   psql "$PG_DSN" -f pg_ddl.sql
--   python -m pytest tests -q          # SQLite 路径 9 例
--   PG_DSN=postgresql://... python -m pytest tests/test_pg_smoke.py -q   # PG 路径
