-- S02 会员在 B 会所报名 A 会所公开活动
-- 执行路径：接口桩 api_register_event（写 event_registration 真实表）；负向用例走同一接口的私有活动校验
TRUNCATE scenario_result;
DO $$
DECLARE v_host TEXT; v_member TEXT; v_ent TEXT; v_rows INTEGER;
        v_blocked BOOLEAN := FALSE; v_msg TEXT;
BEGIN
    SELECT r.host_site, r.member_site, r.ent_id INTO v_host, v_member, v_ent
      FROM api_register_event('V01', 'E01', 'S2') AS r;
    SELECT count(*) INTO v_rows FROM event_registration WHERE event_id = 'V01' AND member_site = 'S2';
    BEGIN
        PERFORM api_register_event('V18', 'E01', 'S2');   -- V18 为 S1 私有活动
    EXCEPTION WHEN OTHERS THEN
        v_blocked := TRUE; v_msg := SQLERRM;
    END;
    INSERT INTO scenario_result (scenario, expected, actual, ok)
    VALUES ('S02',
            '公开活动允许跨会所报名，报名记录带 host_site=S1 与 member_site=S2；私有活动跨会所必须 403',
            format('报名 host=%s member=%s ent=%s 落库 %s 行；私有活动被拒=%s(%s)',
                   v_host, v_member, v_ent, v_rows, CASE WHEN v_blocked THEN 'True' ELSE 'False' END, COALESCE(v_msg, '-')),
            (v_host = 'S1' AND v_member = 'S2' AND v_rows = 1 AND v_blocked));
END $$;
