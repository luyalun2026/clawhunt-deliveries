-- S12 数据导出范围
-- 执行路径：导出走与列表相同的读取路径 api_visible_contacts（单一读取口径），断言导出行全部属于本会所
TRUNCATE scenario_result;
DO $$
DECLARE v_rows INTEGER; v_stray INTEGER; v_expected INTEGER; v_ids TEXT;
BEGIN
    SELECT count(*) INTO v_rows FROM api_visible_contacts('S1');
    SELECT count(*) INTO v_stray FROM api_visible_contacts('S1') WHERE site_id <> 'S1';
    SELECT count(*) INTO v_expected FROM contact WHERE site_id = 'S1' AND deleted_at IS NULL;
    SELECT string_agg(contact_id, ',' ORDER BY contact_id) INTO v_ids FROM api_visible_contacts('S1');
    INSERT INTO scenario_result (scenario, expected, actual, ok)
    VALUES ('S12',
            '导出行严格等于本会所可见范围（含被软删记录已剔除），不含跨会所行',
            format('导出行=%s（应为 %s）；越界行=%s；明细=%s', v_rows, v_expected, v_stray, v_ids),
            (v_stray = 0 AND v_rows = v_expected AND v_rows >= 1));
END $$;
