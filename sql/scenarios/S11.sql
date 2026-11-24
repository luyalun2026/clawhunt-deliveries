-- S11 软删除语义
-- 执行路径：真实 SQL。软删 contact.deleted_at 后：读接口 api_visible_contacts 不再返回该行，
--          但物理记录仍在（审计/历史统计可追溯）。
TRUNCATE scenario_result;
DO $$
DECLARE v_listed INTEGER; v_phys INTEGER; v_deleted_at TEXT;
BEGIN
    UPDATE contact SET deleted_at = '2026-11-20 10:00:00' WHERE id = 'ct-3';
    SELECT count(*) INTO v_listed FROM api_visible_contacts('S1') WHERE contact_id = 'ct-3';
    SELECT count(*), max(deleted_at) INTO v_phys, v_deleted_at FROM contact WHERE id = 'ct-3';
    INSERT INTO scenario_result (scenario, expected, actual, ok)
    VALUES ('S11',
            '软删后不出现在任何列表/导出，但物理记录保留（deleted_at 有值）',
            format('列表命中=%s；物理记录=%s 条 deleted_at=%s', v_listed, v_phys, v_deleted_at),
            (v_listed = 0 AND v_phys = 1 AND v_deleted_at IS NOT NULL));
END $$;
