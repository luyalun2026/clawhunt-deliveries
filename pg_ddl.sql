-- #2762 PostgreSQL 16 专属对象（btree_gist + EXCLUDE 排他约束）。
CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE membership ADD CONSTRAINT no_overlap_active_membership
  EXCLUDE USING gist (
    org_id WITH =,
    company_id WITH =,
    daterange(start_date, COALESCE(end_date, 'infinity'::date), '[)') WITH &&
  )
  WHERE (deleted_at IS NULL AND status <> 'terminated');

ALTER TABLE membership ADD CONSTRAINT ck_mbr_dates
  CHECK (end_date IS NULL OR end_date > start_date);

CREATE INDEX ix_mbr_org_site_status ON membership (org_id, site_id, status);
CREATE INDEX ix_mbr_org_end ON membership (org_id, end_date);
CREATE INDEX ix_mbr_org_company ON membership (org_id, company_id);

-- Alembic：upgrade/downgrade 往返后 alembic check 零漂移——
-- 约束在模型层以 ExcludeConstraint 声明，autogenerate 与本 DDL 一致，
-- EXCLUDE 不会被重复生成（downgrade drop 后 upgrade 重建一次）。
