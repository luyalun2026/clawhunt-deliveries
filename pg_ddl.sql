-- #2763 PG16 专属 DDL 参照（迁移已按方言生成，此文件供 DBA 直接审阅）
-- 部分唯一索引三处
CREATE UNIQUE INDEX uq_contact_org_unionid ON crm_contact (org_id, wechat_unionid)
  WHERE deleted_at IS NULL AND wechat_unionid IS NOT NULL;
CREATE UNIQUE INDEX uq_contact_org_mobile ON crm_contact (org_id, mobile)
  WHERE deleted_at IS NULL AND mobile IS NOT NULL;
CREATE UNIQUE INDEX uq_contact_company_primary ON crm_contact (company_id)
  WHERE member_identity = 'primary' AND deleted_at IS NULL;
