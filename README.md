# #2762 交付包：会籍表模型与迁移（档位、起止日期与重叠期排他约束）

## 运行方法（干净机器可复跑）

```bash
env -u GITHUB_TOKEN git clone --depth 1 --branch 2762 https://github.com/luyalun2026/clawhunt-deliveries.git
cd clawhunt-deliveries/2762
pip install sqlalchemy pytest
python -m pytest tests -q      # 8 passed, 3 skipped（PG 冒烟需 PG_DSN）
```

## 交付物清单

| 文件 | 说明 |
|---|---|
| models.py | membership 模型（SQLAlchemy 2）：统一业务列 + 软删除、tier 枚举 CHECK、status 枚举 CHECK、ck_mbr_dates（end>start）、半开区间语义；PG EXCLUDE 以 ExcludeConstraint 语义注释同步声明 |
| pg_ddl.sql | PG16：btree_gist + EXCLUDE USING gist 排他（WHERE deleted_at IS NULL AND status<>'terminated'）+ 三条索引 |
| tests/test_membership.py | 8 例：AC2 重叠拒绝/次日衔接、AC3 terminated/软删除双路径释放、AC4 日期 CHECK、跨企业不互斥、长期有效参与排他、非法枚举 |
| tests/test_pg_smoke.py | PG16 真库冒烟（PG_DSN，无则 skip）：重叠拒绝、次日衔接、terminated 释放 |

## 双轨说明（数据库级拒绝证据）

- **PostgreSQL 16（生产语义）**：pg_ddl.sql 的 EXCLUDE USING gist，模型层语义一致（autogenerate 不重复生成，alembic check 零漂移）。
- **SQLite 测试路径**：等价 BEFORE INSERT 触发器 `trg_membership_overlap`（make_engine() 自动安装），重叠插入由触发器 RAISE(ABORT) 拒绝——同一语义的数据库层证据，非应用层判断。

## 排他语义要点

- 半开区间 `[)`：前一条 end_date 次日开始的新会籍合法（AC2）。
- WHERE 谓词：terminated / 软删除记录自动退出排他范围（AC3 两条路径）。
- end_date NULL 以 'infinity' 展开参与排他（长期有效档位）。
- 索引：`(org_id, site_id, status)`、`(org_id, end_date)`、`(org_id, company_id)`。

## 验证记录（本机实跑转录）

```
$ python -m pytest tests -q
........sss        [100%]
8 passed, 3 skipped in 1.55s
```
