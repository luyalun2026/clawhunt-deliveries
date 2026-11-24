-- S09 会所级配置（价格规则）
-- 执行路径：接口桩 api_config（site_config 优先，回落 group_config）
TRUNCATE scenario_result;
DO $$
DECLARE v_s1 TEXT; v_s2 TEXT; v_s3 TEXT;
BEGIN
    v_s1 := api_config('S1', 'deposit_ratio_bp');
    v_s2 := api_config('S2', 'deposit_ratio_bp');
    v_s3 := api_config('S3', 'min_lease_months');
    INSERT INTO scenario_result (scenario, expected, actual, ok)
    VALUES ('S09',
            '会所专属配置优先（S1=2000），无专属则回落集团通用（S2=3000），非价格键同样回落（S3 租期=6）',
            format('S1 保证金比例=%s；S2=%s；S3 最短租期=%s', v_s1, v_s2, v_s3),
            (v_s1 = '2000' AND v_s2 = '3000' AND v_s3 = '6'));
END $$;
