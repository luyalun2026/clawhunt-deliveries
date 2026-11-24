-- 口径 1 · 在驻企业数（总部跨会所汇总）
-- 在驻 = enterprise_site.status='in_house' AND ended_at IS NULL，
-- 并排除软删除会所(site.deleted_at)与软删除企业(enterprise.deleted_at)。
-- 同一企业在两个会所入驻计 2（在驻关系数口径）。
SELECT COUNT(*) AS value
FROM enterprise_site es
JOIN site s       ON s.id = es.site_id
JOIN enterprise e ON e.id = es.enterprise_id
WHERE es.status = 'in_house'
  AND es.ended_at IS NULL
  AND s.deleted_at IS NULL
  AND e.deleted_at IS NULL;
