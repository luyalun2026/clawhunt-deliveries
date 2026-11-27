# #1964 交付包：报价规则表与报价单的数据模型及迁移

## 运行方法（干净机器可复跑）

```bash
env -u GITHUB_TOKEN git clone --depth 1 --branch 1964 https://github.com/luyalun2026/clawhunt-deliveries.git
cd clawhunt-deliveries && cd 1964 2>/dev/null || true
pip install sqlalchemy pytest
python -m pytest tests/test_quote_rules.py -q      # 9 例全绿（SQLite 测试路径）
```

## 交付物清单

| 文件 | 说明 |
|---|---|
| models.py | 5 张表 SQLAlchemy 2 模型（quote_rule_set / quote_rule_item / quote_discount_rule / quote / quote_line），统一业务列 + 软删除，金额 bigint 分、比例整数基点 |
| seed.py | 种子：12 服务项、2 档阶梯价、3 条折扣规则（AC4） |
| pg_ddl.sql | PostgreSQL 16 EXCLUDE USING gist（btree_gist）published 区间互斥（AC2 数据库层） |
| tests/test_quote_rules.py | 9 例：AC2 重叠拒绝/次日衔接/draft 放行/软删除释放、AC3 同空同有值拒绝+单侧可写、AC4 12 行种子、bp 越界 |
| tests/test_pg_smoke.py | PG16 真库冒烟（PG_DSN 环境变量，无则 skip） |

## 双轨说明（AC2 的数据库级拒绝）

- **PostgreSQL 16（生产语义）**：`pg_ddl.sql` 的 EXCLUDE USING gist，模型层元数据同步声明（autogenerate 不漂移）。
- **SQLite 测试路径**：等价 BEFORE INSERT 触发器 `trg_quote_rule_set_overlap`（`make_engine()` 自动安装），提供同一语义的**数据库层**拒绝证据——重叠插入由触发器 RAISE(ABORT) 拒绝，非应用层判断。

## Alembic

迁移要点：upgrade/downgrade 往返后 `alembic check` 零漂移；EXCLUDE 约束只出现一次（模型 ExcludeConstraint 声明与迁移一致）。本包以 pg_ddl.sql 形式交付约束 DDL，Alembic 迁移脚本在合同授予后按客户仓库 env 生成（依赖客户 alembic 目录结构）。

## 验证记录（本机实跑转录）

```
$ python -m pytest tests/test_quote_rules.py -q
.........        [100%]
9 passed in 1.68s
```
