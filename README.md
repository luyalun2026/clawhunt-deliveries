# S6-CAL-001 健康分校准特征快照表与数据字典

交付 `calib.health_snapshot`（22 列 = 业务 18 + 汇总/系统 4）、Alembic 迁移、字典单源生成与三项校验脚本。

## 运行

```bash
pip install -r requirements.txt
CALIB_SCHEMA="" python -m pytest tests -q            # 本地 SQLite，13 passed
CALIB_SCHEMA="" python tools/check_dictionary.py     # 业务字段匹配 18/18
CALIB_SCHEMA="" python tools/check_dictionary.py --render   # 生成 dictionary.md / dictionary.csv
CALIB_SCHEMA="" python tools/forbid_sensitive.py     # 敏感列 0 命中
```

生产：`DATABASE_URL=postgresql+psycopg://... alembic upgrade head`（迁移内含 `CREATE SCHEMA IF NOT EXISTS calib`），随后 `python build_snapshot.py --date 2026-12-01`。

## 字段分组

| 组 | 数量 | 字段 |
|---|---|---|
| 维度 | 8 | snapshot_date、company_pid、site_code、industry_code、stage、membership_level、tenure_days、days_to_expiry |
| 原始值 | 5 | event_raw(90d)、interaction_raw(30d)、resource_raw(30d)、opportunity_raw(90d)、space_raw(30d) |
| 标准化分 | 5 | event_score、interaction_score、resource_score、opportunity_score、space_score（0–100） |
| 汇总/系统 | 4 | health_score、health_level、computed_at、algorithm_version |

`dictionary/fields.py` 是唯一事实源：每字段含定义、来源表/口径、取值范围、可空、单位、窗口天数；`dictionary.md`/`csv` 由脚本渲染，不手工维护，因此不会出现文档与实现不一致。

## 关键口径

- `company_pid = HMAC-SHA256(uscc)[:32]`，快照内不存 uscc / name / mobile。
- 任一子项原始值为 NULL → 该子项分与 `health_score`/`health_level` 均为 NULL，**不按 0 补齐**（0 会被误读为最差）。
- `tenure_days = 0` 时，依赖单位天数的派生比率返回 NULL，无除零。
- 标准化函数与生产健康分同一套（`normalize(value, p10, p95)` 截断 0–100），标定表见 `build_snapshot.CALIB`。

## 约束分层

- 数据库 CHECK：数值区间（0–100）、`health_level ∈ {A,B,C,D}`、`tenure_days >= 0`。
- 业务校验 `validate_row()`：`snapshot_date` 必须每月 1 日、`industry_code` 匹配 `^[A-Z][0-9]{2}$`（GB/T 4754-2017 门类+大类）。跨库一致，错误信息可读。

## 验收对照

| 验收项 | 证据 |
|---|---|
| 迁移后表存在、字段与字典一致 | `tools/check_dictionary.py` 输出「业务字段匹配 18/18、缺文档 无、文档多出 无」 |
| 字典覆盖全部字段（定义/来源/取值范围） | `dictionary.md` 22 行 + 测试断言三要素非空 |
| 无 name/uscc/mobile 类字段 | `tools/forbid_sensitive.py` 输出「0 命中」 |

## 边界另测

health_score 101/-1 与 health_level=Z 被 CHECK 拒绝、同日同 pid 重复插入冲突、子项缺失总分 NULL、日期非 1 日与行业码小写/位数不足被业务校验拒绝、tenure_days=0 无除零。
