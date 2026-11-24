-- 口径 3 · 商机转化数（单会所 :site_id）
SELECT op.site_id AS site_id, COUNT(*) AS value
FROM opportunity op
JOIN site s ON s.id = op.site_id
WHERE op.stage = 'signed'
  AND s.deleted_at IS NULL
  AND op.site_id = :site_id
GROUP BY op.site_id;
