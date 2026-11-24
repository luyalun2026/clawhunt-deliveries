-- 口径 5 · 空置工位数（单会所 :site_id）
SELECT s.id AS site_id,
       CASE WHEN COALESCE(occ.occupied, 0) > s.seats
            THEN 0
            ELSE s.seats - COALESCE(occ.occupied, 0)
       END AS value
FROM site s
LEFT JOIN (SELECT es.site_id AS site_id, COUNT(*) AS occupied
           FROM enterprise_site es
           JOIN enterprise e ON e.id = es.enterprise_id
          WHERE es.status = 'in_house'
            AND es.ended_at IS NULL
            AND e.deleted_at IS NULL
          GROUP BY es.site_id) occ ON occ.site_id = s.id
WHERE s.deleted_at IS NULL
  AND s.id = :site_id;
