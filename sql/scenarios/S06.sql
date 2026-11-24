-- S06 知识库「机构共享」文章
-- 执行路径：接口桩 api_read_kb（真实查 knowledge_article，按 scope 过滤）
TRUNCATE scenario_result;
DO $$
DECLARE v_b INTEGER; v_c INTEGER; v_title TEXT; v_scope TEXT;
BEGIN
    SELECT count(*) INTO v_b FROM api_read_kb('kb-org-1', 'S2');
    SELECT count(*) INTO v_c FROM api_read_kb('kb-org-1', 'S3');
    SELECT title, scope INTO v_title, v_scope FROM api_read_kb('kb-org-1', 'S2');
    INSERT INTO scenario_result (scenario, expected, actual, ok)
    VALUES ('S06',
            '机构共享（scope=org）文章在任何有效会所均可读到',
            format('S2 命中 %s 行、S3 命中 %s 行；标题=%s scope=%s', v_b, v_c, v_title, v_scope),
            (v_b = 1 AND v_c = 1 AND v_scope = 'org'));
END $$;
