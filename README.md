# S5-DOC-013 · 含税与不含税金额、税率解析与大小写互校

## 交付内容
- `app/amount.py`：解析与校验模块（纯函数，Decimal 转分整数，禁止 float）
- `data/amount_fixtures.json`：50 条虚构金额写法夹具（小写 25 + 大写 25）
- `tests/test_amount.py`：pytest 测试（AC1–AC4 + 边界）
- `outputs/verify.json`：机器可读验证结果

## 运行与测试
```bash
python -m pytest tests -q
```

## AC 对照
| AC | 要求 | 实现 | 测试 |
|---|---|---|---|
| AC1 | 50 条夹具解析为期望分整数 | `parse_lower_amount` / `parse_upper_amount` | test_ac1_all_50_fixtures_parse_to_expected_fen |
| AC2 | 大小写不一致输出 amount_case_mismatch | `check_and_reconcile` 规则1 | test_ac2_case_mismatch_flags_and_human_review |
| AC3 | 只有含税+税率时不含税留空不推算 | 规则3 | test_ac3_two_items_no_inference |
| AC4 | 无 float 参与金额运算 | AST 扫描浮点字面量/float() | test_ac4_no_float_in_amount_module |

## 四条校验规则
1. 同一金额大小写同时存在须一致，否则 `amount_case_mismatch` + 强制人工核对。
2. 三项齐全校验 `含税 = 不含税 ×(1+税率)`，四舍五入到分、容差 ±1 分，否则 `tax_inconsistent`。
3. 只出现两项时不自动推算第三项，第三项留空并提示补录。
4. 税率不在 {0,1,3,6,9,13}% 时标记 `tax_rate_unusual`，交核对人确认。

## 技术约定
- 金额一律 `Decimal` 解析后转「分」整数（`ROUND_HALF_UP`），禁止 float。
- 税率以 bp 存整数（1300 = 13%）。
- 锚点词：价税合计 / 合同总金额（含税）/ 含税总价 / 不含税金额 / 税率 / 增值税。
- 依赖：无。对接点：调用方传入条款/表格文本，返回结构化 `AmountResult`。
- 样例金额全部虚构。
