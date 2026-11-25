# 会员主数据迁移核对报告

- 生成时间: 2026-11-26T02:41:51
- 源目录: fixtures/perf
- 目标: fixtures/perf/_target
- 抽样: 每对象前 10 条（sampled）
- 差异总数: 0  退出码: 0

## 差异汇总

| 类别 | 数量 |
|---|---|
| count | 0 |
| missing | 0 |
| duplicate | 0 |
| many_to_one | 0 |
| field | 0 |
| credit_code_conflict | 0 |
| orphan_contact | 0 |

## 行数统计

```json
{
 "count_src_companies": {
  "total": 10,
  "by_site": {
   "site-A": 10
  },
  "by_status": {
   "active": 10,
   "soft_deleted": 0
  }
 },
 "count_dst_companies": {
  "total": 10,
  "by_site": {
   "site-A": 10
  },
  "by_status": {
   "active": 10,
   "soft_deleted": 0
  }
 },
 "count_src_contacts": {
  "total": 10,
  "by_site": {
   "site-A": 10
  },
  "by_status": {
   "active": 10,
   "soft_deleted": 0
  }
 },
 "count_dst_contacts": {
  "total": 10,
  "by_site": {
   "site-A": 10
  },
  "by_status": {
   "active": 10,
   "soft_deleted": 0
  }
 },
 "count_src_contact_company": {
  "total": 10,
  "by_site": {
   "site-A": 10
  },
  "by_status": {
   "active": 10,
   "soft_deleted": 0
  }
 },
 "count_dst_contact_company": {
  "total": 10,
  "by_site": {
   "site-A": 10
  },
  "by_status": {
   "active": 10,
   "soft_deleted": 0
  }
 },
 "count_src_tags": {
  "total": 10,
  "by_site": {
   "site-A": 10
  },
  "by_status": {
   "active": 10,
   "soft_deleted": 0
  }
 },
 "count_dst_tags": {
  "total": 10,
  "by_site": {
   "site-A": 10
  },
  "by_status": {
   "active": 10,
   "soft_deleted": 0
  }
 },
 "count_src_tag_objects": {
  "total": 10,
  "by_site": {
   "site-A": 10
  },
  "by_status": {
   "active": 10,
   "soft_deleted": 0
  }
 },
 "count_dst_tag_objects": {
  "total": 10,
  "by_site": {
   "site-A": 10
  },
  "by_status": {
   "active": 10,
   "soft_deleted": 0
  }
 }
}
```

## 字段差异汇总

无字段级差异。
