-- S01 同一会员企业同时入驻两个会所
-- 执行路径：真实 SQL 查 enterprise / enterprise_site（无内存模型）；软删除会所 S9 上的历史关系按有效范围过滤
TRUNCATE scenario_result;
DO $$
DECLARE v_ent INTEGER; v_rel INTEGER; v_sites TEXT; v_raw INTEGER;
BEGIN
    SELECT count(*) INTO v_ent
      FROM enterprise
     WHERE credit_code = (SELECT credit_code FROM enterprise WHERE id = 'E01')
       AND org_id = 'ORG-1' AND deleted_at IS NULL;
    SELECT count(*), string_agg(es.site_id, ',' ORDER BY es.site_id) INTO v_rel, v_sites
      FROM enterprise_site es JOIN site s ON s.id = es.site_id
     WHERE es.enterprise_id = 'E01' AND es.status = 'in_house'
       AND es.ended_at IS NULL AND s.deleted_at IS NULL;
    -- 不做任何过滤的原始关系数（含软删除会所 S9），用于证明过滤真实生效
    SELECT count(*) INTO v_raw FROM enterprise_site WHERE enterprise_id = 'E01' AND status = 'in_house';
    INSERT INTO scenario_result (scenario, expected, actual, ok)
    VALUES ('S01',
            'CRM 中只有一条企业记录，有效入驻关系为两条（S1/S2 各一条；软删会所 S9 的关系不计）',
            format('企业记录 %s 条；有效在驻关系 %s 条（%s）；未过滤原始关系 %s 条',
                   v_ent, v_rel, COALESCE(v_sites, '-'), v_raw),
            (v_ent = 1 AND v_rel = 2 AND v_raw = 3));
END $$;
