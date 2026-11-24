-- 口径 2 · 月度活动场次（总部汇总，:month 形如 '2026-11'）
SELECT COUNT(*) AS value
FROM event ev
JOIN site s ON s.id = ev.site_id
WHERE ev.month = :month
  AND s.deleted_at IS NULL;
