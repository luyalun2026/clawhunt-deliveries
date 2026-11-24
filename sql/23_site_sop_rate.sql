-- 口径 4 · SOP 完成率（单会所 :site_id）
SELECT t.site_id AS site_id,
       SUM(CASE WHEN t.status = 'done' THEN 1 ELSE 0 END) AS done,
       COUNT(*) AS total
FROM sop_task t
JOIN site s ON s.id = t.site_id
WHERE s.deleted_at IS NULL
  AND t.site_id = :site_id
GROUP BY t.site_id;
