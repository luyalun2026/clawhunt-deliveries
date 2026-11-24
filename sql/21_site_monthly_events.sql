-- 口径 2 · 月度活动场次（单会所 :site_id / :month）
SELECT ev.site_id AS site_id, COUNT(*) AS value
FROM event ev
JOIN site s ON s.id = ev.site_id
WHERE ev.month = :month
  AND s.deleted_at IS NULL
  AND ev.site_id = :site_id
GROUP BY ev.site_id;
