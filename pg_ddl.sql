-- #2770 PG16 专属 DDL 参照（迁移已按方言生成）
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX ix_int_org_company_occ ON crm_interaction (org_id, company_id, occurred_at DESC);
CREATE INDEX ix_int_org_contact_occ ON crm_interaction (org_id, contact_id, occurred_at DESC);
CREATE INDEX ix_int_org_owner_occ ON crm_interaction (org_id, owner_user_id, occurred_at DESC);
CREATE INDEX ix_int_summary_trgm ON crm_interaction USING gin (summary gin_trgm_ops);
