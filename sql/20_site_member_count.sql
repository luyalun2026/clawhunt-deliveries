-- 口径 1 · 在驻企业数（单会所 :site_id）
SELECT es.site_id AS site_id, COUNT(*) AS value
FROM enterprise_site es
JOIN site s       ON s.id = es.site_id
JOIN enterprise e ON e.id = es.enterprise_id
WHERE es.status = 'in_house'
  AND es.ended_at IS NULL
  AND s.deleted_at IS NULL
  AND e.deleted_at IS NULL
  AND es.site_id = :site_id
GROUP BY es.site_id;
