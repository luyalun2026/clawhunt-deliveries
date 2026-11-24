-- S10 总部跨会所汇总 = 各会所单独查询之和
-- 执行路径：真实 SQL。每项指标两条独立 SQL：总部口径（一次聚合）与分会所口径（GROUP BY 后求和），
--          另算「去掉软删/离场过滤的朴素计数」，要求朴素值不等于汇总值（排除恒等式自证）。
--          5 项指标的完整 5+5 查询见 sql/10~14_agg_*.sql 与 sql/20~24_site_*.sql，由 tools/run_sql.py 出 sql_results.json。
TRUNCATE scenario_result;
DO $$
DECLARE
    v_m1_t BIGINT; v_m1_s BIGINT; v_m1_n BIGINT;
    v_m2_t BIGINT; v_m2_s BIGINT; v_m2_n BIGINT;
    v_m3_t BIGINT; v_m3_s BIGINT; v_m3_n BIGINT;
    v_m4_t NUMERIC; v_m4_s NUMERIC; v_m4_n NUMERIC;
    v_m5_t BIGINT; v_m5_s BIGINT; v_m5_n BIGINT;
    v_ok BOOLEAN;
BEGIN
    -- 1 在驻企业数
    SELECT count(*) INTO v_m1_t FROM enterprise_site es JOIN site s ON s.id = es.site_id
      JOIN enterprise e ON e.id = es.enterprise_id
     WHERE s.deleted_at IS NULL AND e.deleted_at IS NULL AND es.status = 'in_house' AND es.ended_at IS NULL;
    SELECT COALESCE(sum(c), 0) INTO v_m1_s FROM (
      SELECT count(*) c FROM enterprise_site es JOIN site s ON s.id = es.site_id
        JOIN enterprise e ON e.id = es.enterprise_id
       WHERE s.deleted_at IS NULL AND e.deleted_at IS NULL AND es.status = 'in_house' AND es.ended_at IS NULL
       GROUP BY es.site_id) x;
    SELECT count(*) INTO v_m1_n FROM enterprise_site WHERE status = 'in_house';

    -- 2 月度活动场次 2026-11
    SELECT count(*) INTO v_m2_t FROM event ev JOIN site s ON s.id = ev.site_id
     WHERE s.deleted_at IS NULL AND ev.month = '2026-11';
    SELECT COALESCE(sum(c), 0) INTO v_m2_s FROM (
      SELECT count(*) c FROM event ev JOIN site s ON s.id = ev.site_id
       WHERE s.deleted_at IS NULL AND ev.month = '2026-11' GROUP BY ev.site_id) x;
    SELECT count(*) INTO v_m2_n FROM event WHERE month = '2026-11';

    -- 3 商机签约数
    SELECT count(*) INTO v_m3_t FROM opportunity o JOIN site s ON s.id = o.site_id
     WHERE s.deleted_at IS NULL AND o.stage = 'signed';
    SELECT COALESCE(sum(c), 0) INTO v_m3_s FROM (
      SELECT count(*) c FROM opportunity o JOIN site s ON s.id = o.site_id
       WHERE s.deleted_at IS NULL AND o.stage = 'signed' GROUP BY o.site_id) x;
    SELECT count(*) INTO v_m3_n FROM opportunity WHERE stage = 'signed';

    -- 4 SOP 完成率（分子/分母分别求和后相除）
    SELECT round(sum(CASE WHEN t.status = 'done' THEN 1 ELSE 0 END)::numeric
                 / NULLIF(count(*), 0), 4) INTO v_m4_t
      FROM sop_task t JOIN site s ON s.id = t.site_id WHERE s.deleted_at IS NULL;
    -- 分会所口径：先算各会所完成率，再按样本量 n 加权平均（独立于「分子分母直接相加」的第二条路径）
    SELECT round(sum(round(d::numeric / NULLIF(n, 0), 4) * n) / NULLIF(sum(n), 0), 4) INTO v_m4_s FROM (
      SELECT count(*) FILTER (WHERE t.status = 'done') d, count(*) n
        FROM sop_task t JOIN site s ON s.id = t.site_id WHERE s.deleted_at IS NULL
       GROUP BY t.site_id) x;
    SELECT round(sum(CASE WHEN status = 'done' THEN 1 ELSE 0 END)::numeric
                 / NULLIF(count(*), 0), 4) INTO v_m4_n FROM sop_task;

    -- 5 空置工位数（在驻数超容量按 0 计）
    SELECT COALESCE(sum(GREATEST(s.seats - COALESCE(occ.c, 0), 0)), 0) INTO v_m5_t
      FROM site s LEFT JOIN (
        SELECT es.site_id, count(*) c FROM enterprise_site es JOIN enterprise e ON e.id = es.enterprise_id
         WHERE es.status = 'in_house' AND es.ended_at IS NULL AND e.deleted_at IS NULL
         GROUP BY es.site_id) occ ON occ.site_id = s.id
     WHERE s.deleted_at IS NULL;
    -- 分会所口径：逐会所相关子查询算空置，再求和（与上面的 LEFT JOIN 聚合是两条独立写法）
    SELECT COALESCE(sum(v), 0) INTO v_m5_s FROM (
      SELECT GREATEST(s.seats - (SELECT count(*) FROM enterprise_site es
                                  JOIN enterprise e ON e.id = es.enterprise_id
                                 WHERE es.site_id = s.id AND es.status = 'in_house'
                                   AND es.ended_at IS NULL AND e.deleted_at IS NULL), 0) AS v
        FROM site s WHERE s.deleted_at IS NULL) x;
    SELECT COALESCE(sum(GREATEST(seats - 0, 0)), 0) INTO v_m5_n FROM site;   -- 朴素：不看入驻数

    v_ok := (v_m1_t = v_m1_s AND v_m1_n <> v_m1_t)
        AND (v_m2_t = v_m2_s AND v_m2_n <> v_m2_t)
        AND (v_m3_t = v_m3_s AND v_m3_n <> v_m3_t)
        AND (abs(v_m4_t - v_m4_s) <= 0.0002 AND v_m4_n <> v_m4_t)
        AND (v_m5_t = v_m5_s AND v_m5_n <> v_m5_t);

    INSERT INTO scenario_result (scenario, expected, actual, ok)
    VALUES ('S10',
            '5 项指标总部汇总值 = 各会所单独查询之和，且去掉过滤条件后数值会变（非恒等式）',
            format('在驻企业 %s/%s(朴素%s)；活动 %s/%s(朴素%s)；签约 %s/%s(朴素%s)；SOP 完成率 %s/%s(朴素%s)；空置工位 %s/%s(朴素%s)',
                   v_m1_t, v_m1_s, v_m1_n, v_m2_t, v_m2_s, v_m2_n, v_m3_t, v_m3_s, v_m3_n,
                   v_m4_t, v_m4_s, v_m4_n, v_m5_t, v_m5_s, v_m5_n),
            v_ok);
END $$;
