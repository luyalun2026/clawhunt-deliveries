-- 口径 4 · SOP 完成率（总部）
-- 分子分母分别汇总后相除，避免「先算分率再平均」的辛普森偏差。
SELECT SUM(CASE WHEN t.status = 'done' THEN 1 ELSE 0 END) AS done,
       COUNT(*) AS total
FROM sop_task t
JOIN site s ON s.id = t.site_id
WHERE s.deleted_at IS NULL;
