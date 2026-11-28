-- #2771 PG16 专属 DDL 参照（迁移已按方言生成）
-- 两条补建外键（upgrade）
ALTER TABLE crm_interaction ADD CONSTRAINT fk_interaction_opportunity_id
  FOREIGN KEY (opportunity_id) REFERENCES crm_opportunity(id);
ALTER TABLE crm_lead ADD CONSTRAINT fk_lead_converted_opportunity_id
  FOREIGN KEY (converted_opportunity_id) REFERENCES crm_opportunity(id);
-- 索引
CREATE INDEX ix_opp_org_stage_close ON crm_opportunity (org_id, stage, expected_close_date);
CREATE INDEX ix_opp_org_owner_stage ON crm_opportunity (org_id, owner_user_id, stage);
CREATE INDEX ix_opp_org_company ON crm_opportunity (org_id, company_id);
