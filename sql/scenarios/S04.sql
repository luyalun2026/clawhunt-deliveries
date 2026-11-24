-- S04 会所停业后历史数据只读
-- 执行路径：UPDATE site.status='closed' 后，读走 api_visible_contacts（真实读表）、写走 api_change_contact_owner（409）
TRUNCATE scenario_result;
DO $$
DECLARE v_read INTEGER; v_blocked BOOLEAN := FALSE; v_msg TEXT; v_owner TEXT;
BEGIN
    UPDATE site SET status = 'closed' WHERE id = 'S2';
    SELECT count(*) INTO v_read FROM api_visible_contacts('S2');
    BEGIN
        PERFORM api_change_contact_owner('ct-2', 'owner-x', 'S2');
    EXCEPTION WHEN OTHERS THEN
        v_blocked := TRUE; v_msg := SQLERRM;
    END;
    SELECT owner_id INTO v_owner FROM contact WHERE id = 'ct-2';
    INSERT INTO scenario_result (scenario, expected, actual, ok)
    VALUES ('S04',
            '停业会所读接口正常返回历史数据，写接口 409 且数据未被改动',
            format('读=%s 行；写被拒=%s(%s)；ct-2 负责人仍为 %s',
                   v_read, CASE WHEN v_blocked THEN 'True' ELSE 'False' END, COALESCE(v_msg, '-'), v_owner),
            (v_read >= 1 AND v_blocked AND v_msg LIKE '%409%' AND v_owner = 'owner-s2-b1'));
END $$;
