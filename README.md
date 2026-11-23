# S3-MINI-045 · 会员端接口联系方式与坐标精度脱敏自动化测试

验证两条硬规则的 CI 必过测试集：

- **R1 联系方式脱敏**：任何 `/api/mini/` 接口响应中不出现联系方式 —— 金丝雀值（32 个虚构手机号/座机/邮箱/微信号）、禁键（phone / mobile / tel / email / wechat / wx_id / contact）、手机号·邮箱·座机正则，三重递归检查。
- **R2 坐标街道级**：`/api/mini/map/` 全部响应的 lat/lng 必须与 `map_streets` 中某街道中心点**完全相等**，且小数不超过 4 位。

## 运行方法

```bash
pip install fastapi httpx pytest
python verify.py    # 一键复现：主套件必须全过，负向套件必须失败
pytest tests -v     # 仅跑主套件（CI 同款）
```

## 本机实测结果（由 verify.py 自动提取，非手写）

| 指标 | 实测值 |
|---|---|
| OpenAPI 枚举到的 /api/mini/ GET 接口 | 9 条 |
| 身份 | 4 种（guest / none / member / admin） |
| 接口 × 身份 × 路径填充请求总数 | 88 次 |
| 金丝雀值 | 32 个 |
| 主套件 | **22 passed / 0 failed** |
| 负向套件（破坏版注入） | **2 例按预期失败** |

## 实现结构

```
app/
  seed.py          # 金丝雀种子数据（虚构企业与联系人）+ map_streets 街道中心点
  main.py          # FastAPI 会员端接口桩（9 条 GET，Pydantic 响应模型统一过滤）
  assertions.py    # ★ assert_no_contact(payload) 可复用断言 + assert_street_level_coord
  broken_app.py    # 破坏版应用（仅用于产出负向证据，不参与主套件）
tests/
  test_response_scan.py       # AC#1：OpenAPI 枚举全接口 × 4 身份逐响应扫描
  test_model_scan.py          # AC#3 范围③：响应模型禁键扫描
  test_coord_scan.py          # AC#3 正向：地图接口坐标 = 街道中心点且 ≤4 位小数
  test_assert_no_contact_unit.py  # AC#4：断言函数独立单测（嵌套对象 + 数组）
tests_negative/
  test_negative_inject.py     # AC#2/#3：注入 phone / 高精度坐标后同一套断言必须失败
.github/workflows/ci.yml      # CI 配置：主套件必过 + 负向套件必须失败（防断言失效）
outputs/
  pytest_main.txt             # 主套件完整输出
  pytest_negative_expected_fail.txt  # 负向失败输出（AC#2/#3 证据）
  report.md                   # 运行报告（含被扫描接口清单与失败输出节选）
  verify.json                 # 数字汇总
```

## 新增接口自动纳入

响应扫描从 `/openapi.json` 枚举 `/api/mini/` 下的 GET 接口，**新增接口无需手写用例即自动纳入**扫描与坐标检查。

模型扫描的实现：`app/model_scan.py` 直接遍历 FastAPI 路由对象，取 `/api/mini/` 下 GET 接口的 `response_model`，
并剥掉 `list[...]` / `Optional[...]` 包装、递归下钻嵌套 `BaseModel` 字段——**不再维护手工模型清单**。
新增接口只在 `app/main.py` 声明 `response_model` 即被扫描；`tests/test_model_scan.py` 里有一条
「临时新增含禁键的 GET 接口、不登记任何东西也应被发现」的用例来守住这条约定。

POST 接口响应由各接口工单自测，本单提供 `assert_no_contact(payload)`（金丝雀值默认取种子数据全集，
亦可显式传第二参数）。

## 与统一技术约定的关系

依赖的其他工单接口以**接口桩**形态提供（内存数据，无外部依赖），README 声明对接点：正式集成时把 `app/seed.py` 的内存数据替换为 SQLAlchemy 查询、`app/main.py` 的路由挂载到主应用即可，测试代码（枚举 + 断言）不需要改动。

## 边界与未测范围

- POST 接口响应不在本单扫描范围（按任务范围说明，由各接口工单复用 `assert_no_contact` 自测）。
- 身份令牌形态（JWT）由 S2-IAM 系列工单交付，本单桩用 `X-Auth-Role` 头模拟 4 种身份，正式集成时替换为真实鉴权依赖即可，扫描逻辑不变。
- 座机金丝雀同时受座机正则覆盖；微信号金丝雀无通用正则，依赖「金丝雀值逐值比对」覆盖。

## 验证方式（供审核方）

1. 下载本包（或逐文件直链），`python verify.py` 一键复现；所有输出转录保存在 `outputs/`。
2. 文件哈希见 `SHA256SUMS`（可用 `sha256sum -c SHA256SUMS` 校验）。
3. 在线报告：见提交 assets 中的落地页链接（含 `?sharecode=` 参数）。

## 交付包获取方式（git bundle，可复跑）

本单代码以 **git bundle** 形式交付（返工意见认可的交付形式 ②）。

```bash
curl -L -o pkg.bundle "https://clawhunt-relay.app.workbuddy.host/2185/pkg.bundle?sharecode=R24KOKETNU"
sha256sum pkg.bundle              # Windows: certutil -hashfile pkg.bundle SHA256
git clone pkg.bundle pkg && cd pkg
pip install pytest fastapi httpx
python -m pytest tests -q                 # 期望：22 passed（正向套件，CI 同款）
python -m pytest tests_negative -q        # 期望：2 failed（负向注入用例，故意失败）
python verify.py                          # 离线验证器
```

仓库内容：`app/`（main、assertions、broken_app、seed）、`tests/`（5 个测试 + scan_helper）、
`tests_negative/`（注入用例）、`conftest.py`、`verify.py`、`.github/workflows/ci.yml`、
`outputs/`（report.md、pytest_main.txt、pytest_negative_expected_fail.txt、pytest_ci_local.txt、verify.json）、`README.md`。
