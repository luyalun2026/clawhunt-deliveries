# #2829 招商顾问只能看到本人与公海线索 · 越权用例交付包（v3）

## 交付形式

代码以**公开 GitHub 仓库分支**交付，无需登录即可克隆：

```bash
git clone --branch 2829 https://github.com/luyalun2026/clawhunt-deliveries.git ch2829
cd ch2829
python verify.py          # 一键复现：pytest → junit → 分组统计 → probe 指标 → 报告
```

仓库内包含本单全部可运行文件（含 `verify.py`、`probe.py`），版本可核对：`git log -1 --format=%H`。
`SHA256SUMS` 列出全部受版本管理文件的 SHA-256（本文件、`index.html`、测试与产物均在内）；
如需离线包，可在克隆后执行 `git bundle create 2829.bundle --all` 生成同内容 bundle。

## 一键复现

```bash
python verify.py
```

内部依次执行 `pytest tests -q`（内存 / 接口 / 页面三层）与 `python probe.py`（运行期指标采集），
输出 `outputs/junit.xml`、`verify.json`、`metrics.json`、`matrix.md`、`matrix-cells.md`、`run-report.md`、`summary.json`。
用例数、通过/失败/跳过数由 junit 解析得到，指标由 probe 实测，**无手写数字**。

## 环境

```bash
pip install fastapi uvicorn httpx pytest
pip install playwright && playwright install chromium   # 页面层；无 Chromium 时自动退回本机 Edge
```

- 本轮实测环境：Playwright 1.65 + 本机 Edge（headless），页面层 9 例全部真实执行并通过，**无跳过**。
- Python 3.11+；全部数据虚构，不含真实企业与个人信息。

## 三层证据结构

| 层 | 文件 | 用例数 | 证据形态 |
|---|---|---|---|
| 内存实现 | `app/authz.py` + `tests/test_2829.py` | 29 | 六类操作的返回值与审计落库、80 格资源×操作矩阵 |
| **接口层** | `app/http_api.py` + `tests/test_http_authz.py` | 29 | 真实 `uvicorn` 进程 + `httpx`，断言 401/403/404、CSV 文件行数与内容 |
| **页面层** | 服务端渲染页 + `tests/e2e/test_page_authz.py` | 9 | Playwright 真实浏览器（`X-Actor=A`）：列表、点击、他人详情直达 URL、导出下载、全局搜索 |

身份经请求头 `X-Actor` 注入，与网关认证主体等价；生产替换为 JWT 解析即可，业务判定逻辑完全复用 `app/authz.py`。

## 结构

| 文件 | 说明 |
|---|---|
| `app/authz.py` | 被测系统（内存实现）：列表/详情/报价/合同/改负责人/导出/检索，可见性规则与审计 |
| `app/http_api.py` | FastAPI 真实服务：列表/导出(CSV)/搜索/详情/报价/合同/改归属/审计 + 页面 `/leads`、`/leads/{id}`、`/search`、`/export` |
| `matrix.json` / `_gen_matrix.py` | 资源 × 操作 80 格矩阵，声明式生成，用例反向校验实现 |
| `tests/test_2829.py` | 29 例：AC1–AC4 与边界组 |
| `tests/test_http_authz.py` | 29 例：AC1/AC3(CSV 文件)/AC2 六类越权/AC4 增量对拍/页面 SSR |
| `tests/e2e/test_page_authz.py` | 9 例：列表 8 条、点进本人线索、他人线索 404、匿名 401、搜索 0 条/8 条、导出页行数与 CSV、匿名导出/搜索 401 |
| `probe.py` | 运行期指标采集（列表条数、导出条数、跨租户泄漏、审计对数） |
| `verify.py` | 一键复现 + 报告生成（passed / failed / skipped 分列） |
| `index.html` | 交付说明页：实测数字、分组结果、文件清单（按磁盘实际生成） |
| `outputs/` | junit.xml、verify.json、metrics.json、matrix.md、matrix-cells.md、run-report.md、summary.json、pytest-output.txt |

## 前置数据

顾问 A、B 各 5 条线索，公海 3 条，运营主管 1 名；另设 1 条软删除线索与 1 条他站线索（不计入 13 条基准）。

## 对齐验收标准

| AC | 实现与用例 |
|---|---|
| 1 A 的线索列表恰好 8 条 | 内存 `test_01`–`test_03`；接口 `test_ac1_list_returns_exactly_8`（200 且 total=8、id 集合=本人 5 + 公海 3） |
| 2 六类越权全部被拒，状态码断言 | 内存 `test_04`–`test_09`；接口 8 组参数化 404/403/401 + 导出/搜索两类（`test_ac2_search_*`、`test_ac3_export_*`）；页面 404/401 |
| 3 A 导出的线索文件行数为 8 | 接口 `test_ac3_export_row_count_is_8`：`text/csv` 附件、`X-Export-Rows: 8`、CSV 数据行 8、仅含 A 的 5 条 + 公海 3 条、不含 B 编号；页面 `test_page_export_downloads_csv_with_8_rows` |
| 4 审计条数 = 越权尝试次数 | 内存 `test_13`–`test_16`（42 = 42）；接口 `test_ac4_audit_rows_equal_denied_attempts`（6 次 → +6）、`test_ac4_anonymous_search_and_export_are_audited`（2 次 → +2） |

## 导出与搜索的越权口径（明确说明）

| 操作 | 已认证但越界（A 导出/搜索 B 的数据） | 匿名 |
|---|---|---|
| 导出 `/api/leads/export` | 200，但文件内容按可见范围过滤（8 行，无 B 编号），**不计越权尝试、不写审计** | 401，写入 `access_denied`（`resource_type=export`） |
| 搜索 `/api/search?q=` | 200，结果集为空，**不计越权尝试、不写审计** | 401，写入 `access_denied`（`resource_type=search`） |

口径理由：导出与搜索是「集合级」操作，平台按主体可见范围下发数据，越界表现为结果集裁掉而非单对象 403；
单对象读取（详情/报价/合同/改归属）越界才产生 404/403 + 审计。两类匿名访问均计为越权尝试并有审计记录。

## 页面层断言要点

- `/leads`（`X-Actor: A`）：`#count`=8、`li.lead`=8、不含「虚构乙企业」；点击 `L-A1` 后 `#name`=「虚构甲企业1」。
- 直达 `/leads/L-B1`：404、`#deny`=「未找到」、响应体不含对方企业名；匿名 401「未登录」。
- `/search?q=虚构乙企业`：`#count`=0、`li.lead`=0、不含对方线索；`q=虚构` 时 8 条且无 `L-B*`。
- `/export`：`#rows`=8、链接指向 `/api/leads/export`；同浏览器上下文取回 CSV，9 行（表头+8）且不含 B。
- 匿名访问 `/export`、`/search`：401 +「未登录」。

## 本轮（v3）修复对照

| 返工意见 | 处理 |
|---|---|
| 1 [blocker] 缺搜索接口/页面，六类中两类无接口层证据 | 新增 `GET /api/search` + `/search` 页面；`tests/test_http_authz.py` 增搜索 2 例、参数化增匿名导出/搜索 2 例；e2e 增搜索 2 例 |
| 2 [blocker] 导出只返回 JSON，无文件与行数断言 | `/api/leads/export` 改为真实 CSV 附件（`Content-Disposition`、`X-Export-Rows`）；接口用 csv 解析断言 8 行、9 行含表头、无 B 编号；e2e 取回文件核对 |
| 3 [major] 导出/搜索未纳入 HTTP 参数化与审计口径 | 参数化补 2 例；新增 `test_ac4_anonymous_search_and_export_are_audited`；README「导出与搜索的越权口径」写明是否计越权与审计 |
| 4 [major] Playwright 用例从未执行 | 本轮安装 Playwright + 本机 Edge 实跑，e2e 9 例全部通过并写入 `outputs/junit.xml`；`verify.json` 不再有 skip |
| 5 [minor] 报告把 skip 计为通过、metrics.json 缺失、index.html 与 SHA256SUMS 陈旧、残留他单编号 | `verify.py` 分列 passed/failed/skipped 并真实写出 `outputs/metrics.json`；`index.html` 由实测数据重建；`SHA256SUMS` 重算；已清除他单编号 |
