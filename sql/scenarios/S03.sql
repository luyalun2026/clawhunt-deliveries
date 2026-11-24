-- S03 联系人跨会所更换负责人
-- 执行路径：接口桩 api_change_contact_owner 真实迁移 contact.site_id/owner_id + 写 contact_owner_history；
--          可见性用同一读取路径 api_visible_contacts 在 S1 / S2 两个会所各查一次
TRUNCATE scenario_result;
DO $$
DECLARE v_hist INTEGER; v_site TEXT; v_owner TEXT;
        v_in_s2 INTEGER; v_in_s1 INTEGER;
BEGIN
    PERFORM api_change_contact_owner('ct-1', 'owner-s2-b2', 'S2');
    SELECT count(*) INTO v_hist FROM contact_owner_history WHERE contact_id = 'ct-1';
    SELECT site_id, owner_id INTO v_site, v_owner FROM contact WHERE id = 'ct-1';
    SELECT count(*) INTO v_in_s2 FROM api_visible_contacts('S2') WHERE contact_id = 'ct-1';
    SELECT count(*) INTO v_in_s1 FROM api_visible_contacts('S1') WHERE contact_id = 'ct-1';
    INSERT INTO scenario_result (scenario, expected, actual, ok)
    VALUES ('S03',
            '联系人由 S1 迁至 S2 并换负责人：历史留 1 条；变更后 S2 可见、S1 不可见',
            format('history=%s 条；contact.site=%s owner=%s；S2 可见=%s S1 可见=%s',
                   v_hist, v_site, v_owner, v_in_s2, v_in_s1),
            (v_hist = 1 AND v_site = 'S2' AND v_owner = 'owner-s2-b2' AND v_in_s2 = 1 AND v_in_s1 = 0));
END $$;
