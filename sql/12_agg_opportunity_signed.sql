-- 口径 3 · 商机转化数（stage='signed' 的商机数，总部汇总）
SELECT COUNT(*) AS value
FROM opportunity op
JOIN site s ON s.id = op.site_id
WHERE op.stage = 'signed'
  AND s.deleted_at IS NULL;
