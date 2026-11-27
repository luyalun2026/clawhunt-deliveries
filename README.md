# 工单 #1924 · S5-DOC-013 含税/不含税金额、税率解析与大小写互校

金额一律以「分」存整数，全程 `Decimal` 解析，禁止 float 参与任何金额运算。
大模型不参与数值处理：本模块只做确定性解析与规则校验，可被单测穷举复现。
虚构测试数据，不含任何真实客户/企业/个人信息。

## 一、验收标准逐条对照（pytest 实跑 55 passed）

| 验收标准原文 | 对应交付物 | 验证方式 |
|---|---|---|
| 1. 50 条夹具全部解析为期望的分整数 | `data/fixtures.py`（LOWER 25 + UPPER 20 + RATE 5 = 50） | `test_ac1_fixture_count` + 3 组 parametrize 共 50 断言，全绿 |
| 2. 大小写不一致输出 `amount_case_mismatch` | `app/amounts.py::check_case` / `extract` | `test_ac2_case_mismatch` 断言 flag 出现 |
| 3. 只有含税金额与税率时，不含税保持空不推算 | `app/amounts.py::check_tax`（缺项返回 None） | `test_ac3_no_reverse_infer` 断言 `None` + `needs_manual_fill` |
| 4. 代码中不存在 float 参与金额运算 | `app/amounts.py` 全文 | `test_ac4_no_float_in_source` 用 AST 断言无 float 字面量；`grep -nE 'float'` 仅命中注释 |

> 另有 12 条边界测试（含税/不含税/税率一致性、±1 分容差、税率白名单、独立成行大写金额）全绿。

## 二、校验规则表（由程序执行，大模型不参与）

| 规则 | 触发条件 | 输出标记 | 处理 |
|---|---|---|---|
| 1 大小写互校 | 同一金额小写与大写同时存在且不一致 | `amount_case_mismatch` | 强制人工核对 |
| 2 三项一致性 | 含税/不含税/税率三项齐全，且 含税 ≠ 不含税×(1+税率)（四舍五入到分，容差 ±1 分） | `tax_inconsistent` | 人工核对 |
| 3 缺项不推算 | 三项中缺任意一项 | `needs_manual_fill` | 留空并提示补录，**不自动推算第三项** |
| 4 税率白名单 | 税率不属于 0%/1%/3%/6%/9%/13% | `tax_rate_unusual` | 交核对人确认 |

## 三、模块与解析口径

- `app/amounts.py`：
  - `parse_lower(text)`：小写金额 → 整数分。支持千分位 `,`、货币符号 `¥￥$`、数量级（`万`=×10⁴、`千`=×10³）、可选 `元/圆` 结尾、负号。全程 `Decimal(s) × mult → ×100 → HALF_UP`。
  - `parse_upper(text)`：中文大写 → 整数分。支持 壹至玖、拾佰仟、万亿、圆/元角分整、零占位。按「节」（个/万/亿）四位一段解析。
  - `parse_rate(text)`：税率 → 基点 bp（`13%`→1300）。
  - `check_case / check_tax / is_unusual_rate`：三条确定性校验。
  - `extract(text)`：按锚点词（价税合计/合同总金额（含税）/含税总价、不含税金额、税率/增值税）从条款文本定位并抽取，返回三项 + flags 列表。
- `data/fixtures.py`：50 条虚构金额写法夹具，期望值为「元→分」整数，人工按合同口径核定。
- `tests/test_amounts.py`：pytest，4 条 AC + 边界用例。

## 四、复现（两种等效形式，任选其一）

本单 GitHub 分支 `1924` 与 git bundle 均为**平铺结构**（根目录即 app/、data/、tests/），无额外子目录前缀。

**形式 A：GitHub 公开仓库（免登录）**
```bash
git clone --branch 1924 https://github.com/luyalun2026/clawhunt-deliveries.git
cd clawhunt-deliveries
python -m pytest tests -q                 # 55 passed
```

**形式 B：git bundle（仓库不可用时的等效交付）**
```bash
curl -L -o pkg.bundle "https://clawhunt-relay.app.workbuddy.host/1924/pkg.bundle?sharecode=R24KOKETNU"
git clone pkg.bundle repo && cd repo
python -m pytest tests -q                 # 55 passed
```

金额运算无 float：
`python -c "import ast; t=ast.parse(open('app/amounts.py',encoding='utf-8').read()); print([n.lineno for n in ast.walk(t) if isinstance(n,ast.Constant) and isinstance(n.value,float)])"` → `[]`。

## 五、边界与依赖

- 【依赖】无。纯标准库（`decimal`/`typing`/`ast`），无第三方 SDK，不联网、不向境外发数据。
- 大写 `零` 作占位（如 肆仟零伍圆整 = 400500 分）；`整` 无角分按 0 处理。
- 数量级写法按「元」计（`12.5万` = 12.5 万元 = 12500000 分），符合合同金额惯例。
- 超分精度按 HALF_UP 四舍五入到整分（合同口径，非银行家舍入）。
- 上游接入点：`extract(text)` 接收合同/报价单条款文本，返回结构化金额与 flags；本单不含数据库落库，业务表字段由集成方按统一约定（id UUID / org_id / site_id / 金额分整数）落库。
