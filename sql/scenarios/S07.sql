-- S07 知识库「会所私有」文章
-- 执行路径：接口桩 api_read_kb；跨会所与不存在都必须返回 0 行（404 语义一致，不泄露存在性）
TRUNCATE scenario_result;
DO $$
DECLARE v_own INTEGER; v_cross INTEGER; v_missing INTEGER;
BEGIN
    SELECT count(*) INTO v_own     FROM api_read_kb('kb-s1-1', 'S1');
    SELECT count(*) INTO v_cross   FROM api_read_kb('kb-s1-1', 'S2');
    SELECT count(*) INTO v_missing FROM api_read_kb('kb-none-x', 'S2');
    INSERT INTO scenario_result (scenario, expected, actual, ok)
    VALUES ('S07',
            '会所私有文章仅本会所可读；跨会所与不存在均 0 行（404 语义一致）',
            format('本会所=%s 行；跨会所=%s 行；不存在=%s 行', v_own, v_cross, v_missing),
            (v_own = 1 AND v_cross = 0 AND v_missing = 0));
END $$;
