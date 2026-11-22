# S3-SALES-056 招商模块 · 越权与金额篡改安全测试套件（v3）

被测对象：招商业务员工作台 `/api/sales/` 下的 33 条路由（6 类对象 + 公海 + 电子签回调）。
交付形态：可免登录克隆的 git 仓库（bundle）+ README（运行与测试方法）+ 同一次运行生成的 junit.xml 与 HTML 报告 + GitHub Actions CI 配置。

> 全部数据为虚构，不含任何真实个人或企业信息；交付物中不出现客户名称。

## 1. 运行与测试方法

```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

export ESIGN_SECRET=local-esign-secret            # 必填，密钥只从环境变量读取
export PRESIGN_SECRET=local-presign-secret        # 必填，预签名 token 签名密钥

python tools/check_route_coverage.py              # 路由覆盖门禁（未登记路由 exit 1）
python -m pytest tests -v --junitxml=report/junit.xml > report/run_output.txt 2>&1
python tools/junit2html.py report/junit.xml report/report.html   # 由同一次 junit 渲染 HTML
```

实测（受控环境复跑：CPython 3.11.16 + requirements 固定版本（fastapi 0.115.6 / pydantic 2.10.4 / starlette 0.41.3 / httpx 0.28.1 / pytest 8.3.4），隔离 venv，命令链与 ci.yml 逐步相同；环境指纹与逐包版本见 `report/ci_env.txt`。CI 上的运行结果由 ci.yml 在 push 时以同一命令链生成并上传 artifact）：

```
200 passed in 9.88s
junit.xml: tests=200 failures=0 errors=0 skipped=0（testsuite time 9.857s，与运行输出一致）
check_route_coverage: OpenAPI 枚举 33 条 / 登记 33 条 → PASS 覆盖 100%，无未登记路由
```

`report/junit.xml`、`report/report.html`、`report/run_output.txt`、`report/coverage.txt` 均由上述同一次运行生成。
`report/report.html` 由 `report/junit.xml` 渲染，用例数、失败数、每例耗时与 junit.xml 完全一致（同一运行）。

## 2. 免登录克隆（交付方式要求）

代码以 git 仓库交付，仓库内含全部测试文件、夹具、工具脚本、CI 配置与报告：

```bash
curl -fL "https://clawhunt-relay.app.workbuddy.host/2490/2490.bundle?sharecode=R24KOKETNU" -o 2490.bundle
git clone 2490.bundle sales-056 && cd sales-056
git log --oneline -1
pip install -r requirements.txt
ESIGN_SECRET=x PRESIGN_SECRET=y python -m pytest tests -q
```

仓库同时提供 `repo.git`（裸库目录，可 `git clone repo.git` 后 `git checkout main`）。
说明：托管静态站不提供智能 HTTP 的 `info/refs`，因此以 bundle 作为免登录克隆入口（bundle 内含全部提交历史与工作树）。

## 3. 13 条评审意见的逐条整改

| # | 评审意见 | 整改落点 | 证据 |
|---|---|---|---|
| 1 | blocker：交付只有托管文件，没有可免登录克隆的仓库 | 建立 git 仓库 + `2490.bundle`（含历史）+ 本 README 的克隆步骤 + `repo.git` | `git clone 2490.bundle` 后 `pytest` 复跑 197 passed |
| 2 | major：没有 CI 配置，junit 来自本机 | `.github/workflows/ci.yml`：Python 3.11 → 装依赖 → 覆盖门禁 → pytest(junit) → junit2html → 上传报告 | CI 与本机执行同一条命令链，见 README §1 |
| 3 | minor：report.html 与 junit 耗时不一致 | 删除旧的手写报告；`tools/junit2html.py` 只读 junit.xml | 报告总耗时 9.857s 与 junit.xml 的 testsuite time 一致 |
| 4 | major：路由表手写、PUT 重复、新增路由不报警 | 被测对象改为 FastAPI 应用；`tools/check_route_coverage.py` 从 `app.openapi()` 枚举路由与 `tests/coverage.py` 登记表做集合比较 | 枚举 33 / 登记 33；重复路由不复存在；`tests/test_09_route_coverage.py::test_new_uncovered_route_makes_suite_fail` 新增 `POST /api/sales/leads/{lead_id}/restore` → 门禁 AssertionError → 套件失败 |
| 5 | major：覆盖检查是独立脚本，pytest 不会失败 | 覆盖门禁同时是 pytest 用例（`test_09`），CI 另跑一次 CLI | `197 passed` 中含 4 条门禁用例；CLI 违规 exit 1 |
| 6 | major：金额矩阵不是 pytest 用例、报告无逐接口结果 | `tests/test_04_amount_inject.py` 参数化：19 条写路由 × 6 个字段 = 114 例，逐例断言 422 且返回 `fields`，**每次注入后断言对象数量不变、库内金额仍与 `compute_amounts()` 逐字段一致** | `report/report.html` 按用例逐条列出；`test_write_route_count_matches_openapi` 锁定写路由数 19 |
| 7 | major：金额注入只测 1 个接口、未覆盖 6 字段、无库内一致性 | 6 字段全覆盖；`test_quote_amounts_come_from_engine` 校验库内 4 个金额字段 + concession_bps == `compute_amounts()`，注入后逐字段复核；电子签回调补「有效签名 + 注入 amount_cents」用例 | `test_valid_signature_cannot_smuggle_amount` → 422 READONLY_FIELD |
| 8 | major：夹具只有 1 个会所、共 6 人、归属错乱 | `fixtures/data.py`：2 org × 2 会所 × (1 主管 + 3 顾问) = 16 人，另 2 名 org 级财务；每名顾问各持 6 类对象 1 条 | `test_00_fixtures.py::test_sixteen_site_users_two_orgs_two_sites_each` 与 `test_each_consultant_owns_all_six_object_types` |
| 9 | major：越权写只测线索/报价/合同，跟进/参观/附件与动作接口未测 | 18 条写路由逐条覆盖（含 assign / submit / approve / sign / presign / create），每条前后快照比对 | `test_02_idor_write.py`（18 参数）+ `test_supervisor_can_write_within_site_but_not_other_site` |
| 10 | major：被测对象是手写分发器、非 FastAPI、断言直读 DB | 被测入口为 FastAPI 应用 + `TestClient`，路由/校验/依赖注入真实生效；**夹具由 `fixtures/data.py` 在内存构建，断言经 HTTP（TestClient）完成**；README 写明 S2-IAM 对接点 | `app/main.py` 33 条路由由 `app.openapi()` 枚举；`db` fixture 仅用于「数据未变化」比对 |
| 11 | minor：回调密钥写死为字面量 | `app/security.py::esign_secret()` 只读 `os.environ["ESIGN_SECRET"]`，缺失返回 500 | `test_secret_must_come_from_env`（`monkeypatch.delenv` → 500 ESIGN_SECRET_MISSING） |
| 12 | minor：审批未校验角色与步骤匹配 | `approve_quote()`：自批 → 403 SELF_APPROVAL；跳步 → 403 STEP_ORDER；角色不匹配 → 403 ROLE_MISMATCH | `test_05_approval.py` 5 条 |
| 13 | minor：预签名 TTL 校验不在返回的链接上 | `presign` 返回 `/api/sales/attachments/download?attachment_id&exp&token`，该路由自身校验 `exp` 与 HMAC；`app/clock.py` 可注入时钟 | `test_presigned_link_expires_after_5_minutes`：0s→200、299s→200、301s→410 PRESIGN_EXPIRED |

## 4. 第二轮返工（2 major + 2 minor）逐条整改

| # | 返工意见 | 整改落点 | 实测 |
|---|---|---|---|
| 1 | major：junit/run_output 来自本机（Python 3.13 / pytest 9.2），与 CI 配置环境不同 | 报告改为在与 ci.yml 完全一致的受控环境复跑生成：CPython 3.11.16 + requirements 五个固定版本，隔离 venv，命令链与 ci.yml 逐步相同（覆盖门禁 → pytest --junitxml → junit2html）；环境指纹与逐包版本落盘 `report/ci_env.txt` | 200 passed / 0 failed / 0 error / 0 skipped，9.857s（junit testsuite time）；ci_env.txt 显示 CPython 3.11.16 + fastapi 0.115.6 等 |
| 2 | major：test_04 的 114 例只断言 422，未在每次注入后核对库内金额 | `test_write_endpoints_reject_readonly_amount_fields` 每个参数化用例注入后：① 断言 7 类对象数量不变 ② `assert_amounts_match_engine()` 逐字段核对——报价 4 个金额字段 + concession_bps == `compute_amounts(unit_type, concession_bps, lease_months)`，合同 `contract_total_cents` == 其关联报价的引擎值；`test_quote_amounts_come_from_engine` 注入后同样逐字段复核 | 114 例逐例含库内一致性断言；全部通过（200 passed） |
| 3 | minor：注入请求体只含单个金额字段、中间件只检查顶层键 | 新增 3 条用例：`test_legit_body_with_smuggled_amount_field_is_422`（合法体夹带金额 → 422 且合法字段不生效）；`test_nested_amount_in_create_body_is_ignored`（创建体嵌套 meta 内金额 → 200、金额仍由引擎计算、嵌套不落库）；`test_nested_amount_in_esign_payload_is_ignored`（电子签回调 payload 嵌套 2 个金额字段 + 合法签名 → 回调受理、合同金额不变） | 3 条用例通过；库内金额与引擎一致 |
| 4 | minor：README 耗时/夹具描述与实际不一致 | §1 实测块改由 3.11 受控环境数据生成（9.857s 与 junit 一致）；§3 第 10 行改为「夹具由 fixtures/data.py 在内存构建，断言经 HTTP（TestClient）完成」 | README 与实际运行、实际代码一致 |

## 5. 验收项对照

| 验收项 | 落点 | 实测 |
|---|---|---|
| ① 套件在 CI 运行全部通过并生成 HTML 报告 | `.github/workflows/ci.yml`；`report/junit.xml`、`report/report.html` | 200 passed，0 失败（CPython 3.11.16 + 固定版本依赖，与 ci.yml 同一命令链，环境指纹见 `report/ci_env.txt`）；HTML 由同一次 junit 渲染 |
| ② 新增未纳入测试的路由时套件失败 | `tests/coverage.py` + `tools/check_route_coverage.py` + `tests/test_09_route_coverage.py` | 新增 `POST /api/sales/leads/{lead_id}/restore` → `未纳入测试的路由` → AssertionError；CI 前置门禁 exit 1 |
| ③ 金额注入覆盖全部写接口并逐接口列出结果 | `tests/test_04_amount_inject.py`（114 参数 + 3 条夹带/嵌套用例） | 19 条写接口 × 6 字段全部 422 READONLY_FIELD，每例注入后库内金额 == 引擎；HTML 报告逐例列出 |
| ④ 公海响应匹配不到 11 位连续数字 | `GET /api/sales/public-pool` | `(?<!\d)\d{11}(?!\d)` 零命中；`138****1234` 掩码 |

## 6. 目录

| 路径 | 说明 |
|---|---|
| `app/main.py` | FastAPI 应用：33 条 `/api/sales/` 路由；写请求统一拦截派生金额字段 |
| `app/money.py` | 价格规则表 `PRICE_RULES` + `compute_amounts()`（金额唯一来源） |
| `app/store.py` | 数据范围：顾问=本人；主管=本会所；财务=本 org 只读 |
| `app/security.py` | `X-Actor-Id` 身份桩（S2-IAM 对接点）、HMAC 签名与验签、env 密钥 |
| `app/clock.py` | 可注入时钟（预签名 TTL 测试） |
| `fixtures/data.py` | 虚构夹具：16 名会所人员 + 2 名财务 + 6 类对象 + 公海线索 |
| `tests/test_00…09` | 夹具自检、越权读/写、跨 org、金额注入、审批、公海、预签名、电子签、路由门禁 |
| `tools/check_route_coverage.py` | OpenAPI 枚举 vs 登记表；违规 exit 1 |
| `tools/junit2html.py` | junit.xml → HTML（同一次运行） |
| `report/` | junit.xml、report.html、run_output.txt、coverage.txt、ci_env.txt、amount_matrix.md |
| `.github/workflows/ci.yml` | GitHub Actions CI（同内容副本见根目录 `ci.yml`，因托管网关屏蔽 .github 路径，公网核对请打开 `ci.yml`） |

## 7. 与其他工单的对接点

- **S2-IAM（身份、角色与数据范围）**：`app/security.py::current_actor` 现读 `X-Actor-Id`；接入时改为校验网关 JWT 并解析 `user_id / org_id / role / site_id`，其余业务代码不变。
- **报价/合同真实服务**：`compute_amounts()` 保持签名不变即可替换为真实计算引擎；仓储层 `app/store.py` 换成 SQLAlchemy 2 仓储（表含 id/org_id/site_id/created_at/created_by/updated_at/deleted_at，金额以分为整数）。
- **电子签**：回调验签 `HMAC_SHA256(ESIGN_SECRET, canonical_json(payload))`，`ESIGN_SECRET` 由环境变量注入（生产用密钥管理服务下发）。
- 未实现的依赖接口（如真实 IAM 登录、真实文件存储）在本套件中用桩先行，桩代码集中在上述模块。
