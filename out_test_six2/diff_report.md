# 会员主数据迁移核对报告

- 生成时间: 2026-11-26T02:41:40
- 源目录: fixtures/six_diffs
- 目标: fixtures/six_diffs/_target
- 差异总数: 12  退出码: 1

## 差异汇总

| 类别 | 数量 |
|---|---|
| count | 2 |
| missing | 1 |
| duplicate | 2 |
| many_to_one | 2 |
| field | 3 |
| credit_code_conflict | 1 |
| orphan_contact | 1 |

## 行数统计

```json
{
 "count_src_companies": {
  "total": 30,
  "by_site": {
   "site-A": 30
  },
  "by_status": {
   "active": 30,
   "soft_deleted": 0
  }
 },
 "count_dst_companies": {
  "total": 29,
  "by_site": {
   "site-A": 29
  },
  "by_status": {
   "active": 29,
   "soft_deleted": 0
  }
 },
 "count_src_contacts": {
  "total": 80,
  "by_site": {
   "site-A": 80
  },
  "by_status": {
   "active": 80,
   "soft_deleted": 0
  }
 },
 "count_dst_contacts": {
  "total": 80,
  "by_site": {
   "site-A": 80
  },
  "by_status": {
   "active": 80,
   "soft_deleted": 0
  }
 },
 "count_src_contact_company": {
  "total": 79,
  "by_site": {
   "site-A": 79
  },
  "by_status": {
   "active": 79,
   "soft_deleted": 0
  }
 },
 "count_dst_contact_company": {
  "total": 80,
  "by_site": {
   "site-A": 80
  },
  "by_status": {
   "active": 80,
   "soft_deleted": 0
  }
 },
 "count_src_tags": {
  "total": 20,
  "by_site": {
   "site-A": 20
  },
  "by_status": {
   "active": 20,
   "soft_deleted": 0
  }
 },
 "count_dst_tags": {
  "total": 20,
  "by_site": {
   "site-A": 20
  },
  "by_status": {
   "active": 20,
   "soft_deleted": 0
  }
 },
 "count_src_tag_objects": {
  "total": 20,
  "by_site": {
   "site-A": 20
  },
  "by_status": {
   "active": 20,
   "soft_deleted": 0
  }
 },
 "count_dst_tag_objects": {
  "total": 20,
  "by_site": {
   "site-A": 20
  },
  "by_status": {
   "active": 20,
   "soft_deleted": 0
  }
 }
}
```

## 字段差异汇总

| 字段 | 差异数 |
|---|---|
| industry | 1 |
| name | 1 |
| phone | 1 |
