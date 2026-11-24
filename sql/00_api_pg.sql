-- #2442 · 接口桩（PostgreSQL 16 · PL/pgSQL）
-- 说明：本单 12 个场景必须在 sql/00_schema.sql 建出的测试库上，用真实 SQL 或接口调用执行。
-- 下列函数就是「接口桩」：每一次调用都读写真实表（contact / opportunity / event_registration / ...），
-- 不在 Python 侧维护任何内存模型；SQLSTATE 语义与线上接口一致（停业=409、越权读=0 行即 404）。
-- 仅 PostgreSQL 16 执行；SQLite 复跑时只跑 5+5 汇总 SQL，不跑本文件。

-- 409：会所停业后写接口只读
CREATE OR REPLACE FUNCTION api_assert_site_writable(p_site TEXT) RETURNS void AS $$
DECLARE v_status TEXT;
BEGIN
    SELECT status INTO v_status FROM site WHERE id = p_site;
    IF v_status = 'closed' THEN
        RAISE EXCEPTION 'HTTP_409 site % closed: read-only', p_site USING ERRCODE = 'P0001';
    END IF;
END;
$$ LANGUAGE plpgsql;

-- 联系人更换负责人（可跨会所迁移）：写 contact_owner_history + 改 contact.site_id/owner_id
CREATE OR REPLACE FUNCTION api_change_contact_owner(p_contact TEXT, p_new_owner TEXT, p_new_site TEXT)
RETURNS void AS $$
DECLARE v_owner TEXT; v_site TEXT; v_id INTEGER;
BEGIN
    SELECT owner_id, site_id INTO v_owner, v_site FROM contact WHERE id = p_contact AND deleted_at IS NULL;
    IF v_owner IS NULL THEN
        RAISE EXCEPTION 'HTTP_404 contact % not found', p_contact USING ERRCODE = 'P0001';
    END IF;
    PERFORM api_assert_site_writable(v_site);
    PERFORM api_assert_site_writable(p_new_site);
    SELECT COALESCE(MAX(id), 0) + 1 INTO v_id FROM contact_owner_history;
    INSERT INTO contact_owner_history (id, contact_id, from_owner, to_owner, from_site, to_site, changed_at)
    VALUES (v_id, p_contact, v_owner, p_new_owner, v_site, p_new_site, '2026-11-20 10:00:00');
    UPDATE contact SET owner_id = p_new_owner, site_id = p_new_site WHERE id = p_contact;
END;
$$ LANGUAGE plpgsql;

-- 商机转介：写 referral + 把 opportunity 的归属会所/负责人改到目标会所
CREATE OR REPLACE FUNCTION api_transfer_opportunity(p_opp TEXT, p_to_site TEXT, p_to_owner TEXT)
RETURNS void AS $$
DECLARE v_site TEXT; v_owner TEXT; v_id INTEGER;
BEGIN
    SELECT site_id, owner_id INTO v_site, v_owner FROM opportunity WHERE id = p_opp;
    IF v_site IS NULL THEN
        RAISE EXCEPTION 'HTTP_404 opportunity % not found', p_opp USING ERRCODE = 'P0001';
    END IF;
    PERFORM api_assert_site_writable(v_site);
    PERFORM api_assert_site_writable(p_to_site);
    SELECT COALESCE(MAX(id), 0) + 1 INTO v_id FROM referral;
    INSERT INTO referral (id, opportunity_id, from_site, to_site, from_owner, to_owner, created_at)
    VALUES (v_id, p_opp, v_site, p_to_site, v_owner, p_to_owner, '2026-11-20 10:00:00');
    UPDATE opportunity SET site_id = p_to_site, owner_id = p_to_owner WHERE id = p_opp;
END;
$$ LANGUAGE plpgsql;

-- 报名活动：公开活动允许跨会所报名，私有活动仅主办会所会员可报（否则 403）
CREATE OR REPLACE FUNCTION api_register_event(p_event TEXT, p_ent TEXT, p_member_site TEXT)
RETURNS TABLE (event_id TEXT, host_site TEXT, member_site TEXT, ent_id TEXT) AS $$
DECLARE v_host TEXT; v_vis TEXT; v_id INTEGER;
BEGIN
    SELECT site_id, visibility INTO v_host, v_vis FROM event WHERE id = p_event;
    IF v_host IS NULL THEN
        RAISE EXCEPTION 'HTTP_404 event % not found', p_event USING ERRCODE = 'P0001';
    END IF;
    IF v_vis <> 'public' AND v_host <> p_member_site THEN
        RAISE EXCEPTION 'HTTP_403 event % not visible to %', p_event, p_member_site USING ERRCODE = 'P0001';
    END IF;
    SELECT COALESCE(MAX(id), 0) + 1 INTO v_id FROM event_registration;
    INSERT INTO event_registration (id, event_id, ent_id, member_site, host_site, created_at)
    VALUES (v_id, p_event, p_ent, p_member_site, v_host, '2026-11-20 10:00:00');
    RETURN QUERY SELECT p_event, v_host, p_member_site, p_ent;
END;
$$ LANGUAGE plpgsql;

-- 知识库读取：机构共享全会所可读；会所私有跨会所返回 0 行（上层 404，不泄露存在性）
CREATE OR REPLACE FUNCTION api_read_kb(p_article TEXT, p_site TEXT)
RETURNS TABLE (id TEXT, title TEXT, scope TEXT, site_id TEXT) AS $$
BEGIN
    RETURN QUERY
    SELECT a.id, a.title, a.scope, a.site_id
      FROM knowledge_article a
     WHERE a.id = p_article
       AND (a.scope = 'org' OR a.site_id = p_site);
END;
$$ LANGUAGE plpgsql;

-- 机构级字典 + 会所扩展（会所可新增键，不可覆写机构键 → 409）
CREATE OR REPLACE FUNCTION api_upsert_site_dict(p_site TEXT, p_dict_key TEXT, p_code TEXT, p_label TEXT)
RETURNS void AS $$
DECLARE v_org_label TEXT;
BEGIN
    SELECT label INTO v_org_label FROM dict_entry
     WHERE dict_key = p_dict_key AND code = p_code AND scope = 'org';
    IF v_org_label IS NOT NULL AND v_org_label <> p_label THEN
        RAISE EXCEPTION 'HTTP_409 cannot override org dictionary key %', p_code USING ERRCODE = 'P0001';
    END IF;
    INSERT INTO dict_entry (dict_key, code, label, scope, site_id)
    VALUES (p_dict_key, p_code, p_label, 'site', p_site)
    ON CONFLICT (dict_key, code, scope, site_id) DO UPDATE SET label = EXCLUDED.label;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION api_dict_entries(p_site TEXT, p_dict_key TEXT)
RETURNS TABLE (code TEXT, label TEXT, scope TEXT) AS $$
BEGIN
    RETURN QUERY
    SELECT d.code, d.label, d.scope
      FROM dict_entry d
     WHERE d.dict_key = p_dict_key
       AND (d.scope = 'org' OR d.site_id = p_site)
     ORDER BY d.code;
END;
$$ LANGUAGE plpgsql;

-- 会所级配置：会所专属优先，无则回落集团通用
CREATE OR REPLACE FUNCTION api_config(p_site TEXT, p_key TEXT) RETURNS TEXT AS $$
DECLARE v TEXT;
BEGIN
    SELECT cfg_value INTO v FROM site_config WHERE site_id = p_site AND cfg_key = p_key;
    IF v IS NULL THEN
        SELECT cfg_value INTO v FROM group_config WHERE cfg_key = p_key;
    END IF;
    RETURN v;
END;
$$ LANGUAGE plpgsql;

-- 可见联系人（导出与列表的唯一读取路径：按会所 + 排除软删除）
CREATE OR REPLACE FUNCTION api_visible_contacts(p_site TEXT)
RETURNS TABLE (contact_id TEXT, ent_id TEXT, site_id TEXT) AS $$
BEGIN
    RETURN QUERY
    SELECT c.id, c.ent_id, c.site_id
      FROM contact c
     WHERE c.site_id = p_site AND c.deleted_at IS NULL
     ORDER BY c.id;
END;
$$ LANGUAGE plpgsql;

-- 商机读取（按会所视角）：本会所返回完整字段；跨会所仅返回脱敏摘要（无金额、无企业ID）
CREATE OR REPLACE FUNCTION api_read_opportunity_as_site(p_opp TEXT, p_site TEXT)
RETURNS jsonb AS $$
DECLARE v RECORD; v_ent_name TEXT;
BEGIN
    SELECT o.id, o.site_id, o.stage, o.ent_id, o.owner_id, o.amount_cent
      INTO v FROM opportunity o WHERE o.id = p_opp;
    IF v.id IS NULL THEN
        RETURN NULL;
    END IF;
    SELECT name INTO v_ent_name FROM enterprise WHERE id = v.ent_id;
    IF v.site_id = p_site THEN
        RETURN jsonb_build_object('id', v.id, 'stage', v.stage, 'owner_id', v.owner_id,
                                  'ent_id', v.ent_id, 'ent_name', v_ent_name,
                                  'amount_cent', v.amount_cent);
    END IF;
    RETURN jsonb_build_object('id', v.id, 'stage', v.stage, 'ent_name', '某企业（脱敏）');
END;
$$ LANGUAGE plpgsql;
