# #2829 招商顾问只能看到本人与公海线索 · 越权用例交付包（v2）

## 交付形式（返工意见一）

代码以**公开 GitHub 仓库分支**交付，无需登录即可克隆：

```bash
git clone --branch 2829 https://github.com/luyalun2026/clawhunt-deliveries.git ch2829
cd ch2829
python verify.py          # 一键复现：pytest + probe + 矩阵 + 报告
```

仓库内包含本单全部可运行文件（含 `verify.py`、`probe.py`，解决返工意见三），
版本可核对：`git log -1 --format=%H`。

如需离线包，可在克隆后执行 `git bundle create 2829.bundle --all` 生成同内容 bundle；
`SHA256SUMS` 列出全部受版本管理文件的 SHA-256，可用于核对「交付时的那一份」。

## 一键复现

```bash
python verify.py
```

内部依次执行 `pytest tests -q`（接口/内存/页面三层）与 `python probe.py`（运行期指标采集），
输出 `outputs/junit.xml`、`outputs/verify.json`、`outputs/matrix.md`、`outputs/run-report.md`。
用例数与通过率由 junit 解析得到，指标由 probe 实测，**无手写数字**。

## 环境

```bash
pip install fastapi uvicorn httpx pytest openpyxl
pip install playwright && playwright install chromium   # 仅页面层用例需要
```

- 无 Playwright 时 `tests/e2e/test_page_authz.py` 整体 skip，其余用例照常执行。
- Python 3.11+；全部数据虚构，不含真实企业与个人信息。

## 三层证据结构（返工意见二）

| 层 | 文件 | 证据形态 |
|---|---|---|
| 内存实现 | `app/authz.py` + `tests/test_2829.py`（29 例） | 6 类操作的返回值与审计落库 |
| **接口层** | `app/http_api.py` + `tests/test_http_authz.py`（17 例） | 真实 `uvicorn` 进程 + `httpx` 请求，断言 401/403/404 |
| **页面层** | 同左（服务端渲染 `/leads`、`/leads/{id}`）+ `tests/e2e/test_page_authz.py`（4 例） | Playwright 真实浏览器携带 `X-Actor=A` 点击与直达 URL |

身份经请求头 `X-Actor` 注入，与网关认证主体等价；生产替换为 JWT 解析即可，业务判定逻辑完全复用 `app/authz.py`。

## 结构

| 文件 | 说明 |
|---|---|
| `app/authz.py` | 被测系统（内存实现）：列表/详情/报价/合同/改负责人/导出/检索，可见性规则与审计 |
| `app/http_api.py` | FastAPI 真实服务：6 个接口端点 + 2 个服务端渲染页面 + `/healthz` |
| `matrix.json` / `_gen_matrix.py` | 资源 × 操作 80 格矩阵，声明式生成，用例反向校验实现（避免自证） |
| `tests/test_2829.py` | 29 例：AC1–AC4 与边界组 |
| `tests/test_http_authz.py` | 17 例：真实 HTTP 服务上的 AC1/AC3/AC2 六类越权/AC4 增量对拍/页面层 3 例 |
| `tests/e2e/test_page_authz.py` | 4 例：Playwright 页面层（列表 8 条、点进本人线索、他人线索 404、匿名 401） |
| `probe.py` | 运行期指标采集（列表条数、导出条数、跨租户泄漏、审计对数） |
| `verify.py` | 一键复现 + 报告生成 |
| `outputs/` | junit.xml、verify.json、matrix.md、run-report.md、summary.json、metrics.json |

## 前置数据

顾问 A、B 各 5 条线索，公海 3 条，运营主管 1 名；另设 1 条软删除线索与 1 条他站线索（不计入 13 条基准）。

## 对齐验收标准

| AC | 实现与用例 |
|---|---|
| 1 A 的线索列表恰好 8 条 | 内存 `test_01`–`test_03`；接口 `test_ac1_list_returns_exactly_8`（HTTP 200 且 total=8） |
| 2 6 类越权全部被拒，状态码断言 | 内存 `test_04`–`test_09`；接口 `test_ac2_denied_over_http`（8 参数化：详情/报价/合同/改归属/匿名/他站/软删除/未知主体→404/403/401）；页面 `test_page_other_lead_denied`（HTTP 404 + 页面显示「未找到」） |
| 3 A 导出的线索文件行数为 8 | 内存 `test_10`–`test_12`；接口 `test_ac3_export_row_count_is_8` |
| 4 审计记录条数 = 越权尝试次数 | 内存 `test_13`–`test_16`（矩阵 42 拒绝 = 42 审计）；接口 `test_ac4_audit_rows_equal_denied_attempts`（6 次尝试 → 增量恰 6） |

## 页面层断言要点

- `/leads` 携带 `X-Actor: A`：`#count` 文本为 `8`，`li.lead` 节点数 8，页面不含「虚构乙企业」。
- 点击 `li.lead[data-id='L-A1'] a.open` 跳转后 `#name` 为「虚构甲企业1」。
- 直达 `/leads/L-B1`：HTTP 404，`#deny` 为「未找到」，响应体不含对方企业名。
- 无 `X-Actor`：HTTP 401，`#deny` 为「未登录」。

## 本轮修复对照

| 返工意见 | 处理 |
|---|---|
| 1 [blocker] 交付形式 | 改为公开 GitHub 仓库分支（免登录 clone），SHA256SUMS 列全量哈希；README 随包 |
| 2 [blocker] 越权只在内存实现 | 新增 `app/http_api.py` 真实服务 + `tests/test_http_authz.py` 17 例（httpx）+ `tests/e2e/test_page_authz.py` 4 例（Playwright） |
| 3 [major] verify.py/probe.py 不在交付内 | 两文件均在仓库根目录，`python verify.py` 可直接复跑；README 已写明 |
