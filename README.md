# 2506 · S3-SOP-005 SOP 模板 JSON 规范、导入导出与 sop-lint

## 运行方法

```bash
pip install -r requirements.txt    # jsonschema / fastapi / uvicorn / httpx / pytest
python -m pytest tests -q          # 7 例测试（1 例防御层在 schema 覆盖下跳过）
python sop_lint/cli.py valid       # -> [OK] 共 0 个错误，退出码 0
python sop_lint/cli.py errors      # -> 逐条 [FAIL]，退出码 1
uvicorn app.main:app --port 8600   # 导入/导出接口
```

## 交付物

- `schema/sop-template.schema.json`：draft-07 Schema（模板/步骤/触发/条件/输出表单/检查项/关联资产）
- `app/sop_core.py` + `app/main.py`：`GET /api/sop/templates/{id}/export`、`POST /api/sop/templates/import`（草稿 + warnings 不静默丢弃）
- `sop_lint/cli.py`：7 类检查（schema_invalid / role_unknown / due_rule_invalid / seq_duplicate / trigger_event_unknown / depends_on_cycle / condition_field_unknown）
- `catalogs/catalogs.json`：岗位 4 / 知识文档 3 / 事件类型 4 目录种子（接口桩）
- `errors/`：7 类错误样例各 1 个；`valid/`：全绿样例
- `tests/`：往返相等 / 7 类规则识别 / 退出码 / warnings / 自环 / 空目录 / 404

## 验收标准落点

| AC | 证据 |
|---|---|
| 1 往返逐字段相等 | `test_ac1_roundtrip_equal`：export→import→export 后 sort_keys JSON 逐字节相等 |
| 2 识别 ≥6 类错误 | `test_ac2_lint_seven_rules`：7 个样例文件，识别规则 ≥6 类 |
| 3 错误退出码非 0 | `test_ac3_lint_exit_codes`：errors→1，valid→0 |
| 4 解析不到引用进 warnings | `test_ac4_import_warnings`：3 类未解析引用均在 warnings，草稿照常落库 |

## 对接点（接口桩）

岗位 / 知识文档 / 事件类型目录为 `catalogs/catalogs.json` 内置种子；正式接入时替换 `sop_core.load_catalogs` 数据源即可。
