-- S05 商机从 A 会所转介到 B 会所
-- 执行路径：接口桩 api_transfer_opportunity（写 referral + 改 opportunity.site_id），
--          随后以 A、B 两个会所身份各走一次真实读取路径 api_read_opportunity_as_site，断言返回字段集合
TRUNCATE scenario_result;
DO $$
DECLARE v_site TEXT; v_refs INTEGER; v_ref_site TEXT;
        j_a JSONB; j_b JSONB; k_a TEXT; k_b TEXT;
BEGIN
    PERFORM api_transfer_opportunity('O01', 'S2', 'owner-s2-b1');
    SELECT site_id INTO v_site FROM opportunity WHERE id = 'O01';
    SELECT count(*), max(from_site) INTO v_refs, v_ref_site FROM referral WHERE opportunity_id = 'O01';
    j_a := api_read_opportunity_as_site('O01', 'S1');   -- A 会所（转出方）视角
    j_b := api_read_opportunity_as_site('O01', 'S2');   -- B 会所（接收方）视角
    SELECT string_agg(k, ',' ORDER BY k) INTO k_a FROM jsonb_object_keys(j_a) AS k;
    SELECT string_agg(k, ',' ORDER BY k) INTO k_b FROM jsonb_object_keys(j_b) AS k;
    INSERT INTO scenario_result (scenario, expected, actual, ok)
    VALUES ('S05',
            'site_id 改为 S2 + 转介记录 1 条；A 会所仅见脱敏摘要（无 amount_cent / ent_id），B 会所见完整字段',
            format('site=%s 转介=%s 条(from=%s)；A 视角字段={%s}；B 视角字段={%s} 金额=%s',
                   v_site, v_refs, v_ref_site, k_a, k_b, j_b ->> 'amount_cent'),
            (v_site = 'S2' AND v_refs = 1 AND v_ref_site = 'S1'
             AND j_a ? 'id' AND j_a ? 'stage' AND j_a ? 'ent_name'
             AND NOT (j_a ? 'amount_cent') AND NOT (j_a ? 'ent_id') AND NOT (j_a ? 'owner_id')
             AND j_b ? 'amount_cent' AND (j_b ->> 'amount_cent') = '1200000'));
END $$;
