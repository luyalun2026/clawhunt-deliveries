-- S08 机构级字典（空间类型）
-- 执行路径：接口桩 api_upsert_site_dict（写 dict_entry 真实表）+ api_dict_entries 读回
TRUNCATE scenario_result;
DO $$
DECLARE v_blocked BOOLEAN := FALSE; v_msg TEXT; v_cnt INTEGER; v_has_coworking INTEGER;
BEGIN
    BEGIN
        PERFORM api_upsert_site_dict('S2', 'space_type', 'office', '办公室（S2 自定义）');
    EXCEPTION WHEN OTHERS THEN
        v_blocked := TRUE; v_msg := SQLERRM;
    END;
    PERFORM api_upsert_site_dict('S2', 'space_type', 'coworking', '联合办公');  -- 允许会所新增键
    SELECT count(*) INTO v_cnt FROM api_dict_entries('S2', 'space_type');
    SELECT count(*) INTO v_has_coworking FROM api_dict_entries('S2', 'space_type') WHERE code = 'coworking';
    INSERT INTO scenario_result (scenario, expected, actual, ok)
    VALUES ('S08',
            '覆写机构键被 409 拒绝；会所新增键生效（S2 视角 3 个空间类型）',
            format('覆写被拒=%s(%s)；S2 字典 %s 项；coworking 生效=%s',
                   CASE WHEN v_blocked THEN 'True' ELSE 'False' END, COALESCE(v_msg, '-'), v_cnt, v_has_coworking),
            (v_blocked AND v_msg LIKE '%409%' AND v_cnt = 3 AND v_has_coworking = 1));
END $$;
