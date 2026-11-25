# 2206 · S5-INTEL-017 情报分类标签体系定义与会员 CRM 标签映射

## 运行方法

```bash
pip install pyyaml
python -m pytest tests -q                          # 6 例测试
python tools/import_tags.py --seed seed/intel_tags.yaml --db intel.db      # 幂等导入
python tools/import_tags.py --seed seed/intel_tags.yaml --db intel.db      # 再跑一次计数不变
python tools/validate_tags.py --seed seed/intel_tags.yaml                  # 40/40 校验
python tools/import_tags.py --seed seed/intel_tags.yaml --emit-sql         # PG 版 upsert SQL
```

## 交付物

- `seed/intel_tags.yaml`：5 维度种子（policy_type 10 / industry 14 / qualification 8 / region 4 / company_size 4 = 40 标签），每标签含 code/名称/定义≤50 字/正例 2 条/反例 1 条/crm_tag_code
- `tools/import_tags.py`：以 (dimension, code) 唯一键 upsert，重复执行幂等
- `tools/validate_tags.py`：必填非空 / 定义字数 / 正反示例齐全校验
- `docs/crm_mapping.md`：industry→crm_tag_code 映射表 + missing 待确认清单（agriculture / culture_tourism）
- `tests/`：维度计数 / 幂等 / 校验 / 映射回链 / 重复 code 拒绝 / 定义超长拦截

## 验收标准落点

| AC | 证据 |
|---|---|
| 1 维度计数 | `test_ac1_dimension_counts`：5 维度、10/14/8/4/4 |
| 2 幂等导入 | `test_ac2_idempotent_import`：两次导入计数不变；CLI 实跑 inserted=40 total_after=40 |
| 3 校验脚本 | `test_ac3_validate_script`：40/40 全通过；残缺种子退出码非 0 |
| 4 映射与 missing | `test_ac4_mapping_and_missing`：12 映射 + 2 缺失项单独列出 |

## 对接点（接口桩）

SQLite 演示表 `intel_tags`；正式 PG 表用 `--emit-sql` 输出 `INSERT ... ON CONFLICT` 语句。
