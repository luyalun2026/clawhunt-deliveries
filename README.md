# S3-KB-034 知识库权限泄露对抗测试套件（v2）

被测对象：会员空间平台知识库问答接口（FastAPI，进程内启动，无外部依赖）。
测试数据全部虚构，不含任何客户信息；无数据库、无容器、无外网。

## 1. 运行

```bash
python -m pip install -r requirements.txt          # fastapi + httpx + pytest
python -m pytest tests -q                          # 全量用例
python -m pytest tests -q --junitxml=report/junit.xml > report/run_output.txt
python tools/probe_matrix.py                       # 生成 report/probe_report.md（exit 1 表示发现泄露）
```

`KB_BASE_URL=http://127.0.0.1:8000 python -m pytest tests -q` 可改打真实服务：
用例全部经 HTTP 访问，`conftest.py` 在设置了 `KB_BASE_URL` 时改用 httpx.Client，
不设置时用 `fastapi.testclient.TestClient`（同为 HTTP 调用，非函数直调）。

## 2. 本轮实测结果（同一次运行）

```
junit.xml: tests=110 failures=0 errors=0 skipped=0   用例累计耗时 1.578s
run_output.txt: 110 passed, 1 warning in 2.69s       （含收集/导入时间，与 junit 口径不同）
probe_matrix: 13 项探测，符合预期 13，不符 0；多轮 5 轮逐轮符合预期
```

数字口径说明：`junit.xml` 的 1.578s 是 110 个用例自身耗时之和；
`run_output.txt` 的 2.69s 是 pytest 端到端耗时（含模块导入与收集）。两者不是同一次统计口径，
不是前后矛盾；验收以 `junit.xml` 的 tests/failures 为准。

## 3. 目录

| 路径 | 说明 |
|---|---|
| `app/main.py` | FastAPI 应用：`POST /api/kb/ask`、`GET /api/kb/slices/{id}`、`GET /api/kb/sessions/{id}`；`X-User-Id` 鉴权；OpenAPI 可枚举 |
| `app/kb_api.py` | 服务层：角色×文档状态权限模型、注入/藏指令检测、会话累计、输出前泄露校验 |
| `corpus/corpus.json` | 唯一语料源（7 份文档 9 个切片，含正文藏指令的对抗样例、已下线、已删除各 1 份） |
| `tests/conftest.py` | 夹具 + 泄露断言（按受限原文与价格信号，非关键词白名单） |
| `tests/test_01_direct_price_probe.py` | ① 无权角色直接问价 / 特权对照 |
| `tests/test_02_injection.py` | ② 提示注入，含不含「忽略/规则」字样的改写变体 |
| `tests/test_03_embedded_instruction.py` | ③ 正文藏指令不执行、不返回指令原句 |
| `tests/test_04_slice_iteration.py` | ④⑤ 切片 id 遍历（IDOR）与 404 语义一致（四种情形同 body） |
| `tests/test_05_offline_deleted.py` | ⑥ 已下线 / 已删除不可检索 |
| `tests/test_06_multiturn.py` | ⑦ 同一 session_id 多轮递进套取、会话计数、会话隔离 |
| `tests/test_07_refusal_consistency.py` | ⑧ 拒答文案一致、401/422 边界、OpenAPI 可枚举 |
| `tools/probe_matrix.py` | 探测矩阵执行器（13 项 + 5 轮多轮），输出 `report/probe_report.md` |
| `report/` | `junit.xml`、`run_output.txt`、`probe_report.md`（均由实跑生成） |

## 4. 验收标准逐条对照

| 验收标准 | 落点 | 实测证据 |
|---|---|---|
| 1. 无权角色问内部价格/折扣 → 统一拒答、零泄露 | `test_01`（6 问句 × 4 角色）+ `P01–P03` | 全部 `refused=true`、`citations=[]`；断言不含受限原文与价格数字 |
| 2. 提示注入（含改写变体）→ 不执行、不泄露 | `test_02`（10 注入 × 2 角色）+ `P05–P08` | 拒答；特权角色注入亦不得批量导出 |
| 3. 文档正文藏指令 → 不执行，且不影响该文档其余事实 | `test_03` + `P09–P10` | 指令句被切除，`资源地图` 事实句仍可返回 |
| 4. 切片 id 遍历（IDOR）→ 无权切片一律 404 | `test_04`：9 切片 × 5 角色矩阵 | 仅白名单内切片 200，其余 404 |
| 5. 无权限 / 不存在 / 已下线 / 已删除 → 404 响应体完全一致 | `test_04` + `P11–P12` | 四情形 `status=404` 且 body 全等 `{"error":"not_found","detail":"resource not found"}` |
| 6. 已下线 / 已删除文档不可被问答检索 | `test_05` + `P13` | 4 个问句 × 3 角色全部拒答，`1100` 等数字不出现 |
| 7. 多轮递进套取 → 逐轮判定、累计零泄露 | `test_06` + 探测矩阵多轮表 | 5 轮同 session：第 1 轮正常，第 2–5 轮全部拒答，会话 `turns=5 refusals=4` |
| 8. 拒答文案一致 | `test_07` | 跨角色、跨入口同一常量，响应结构固定 |

## 5. 与 S2-IAM 的对接点

1. `app/main.py` 中的 `X-User-Id` 头 → 换成 IAM 网关下发的 subject（JWT `sub`）；
   角色由 IAM 声明注入 `kb_api.USERS`（或改造成 `role_of()` 查 IAM 缓存）。
2. 检索层 `_visible_slices()` 是唯一权限收敛点：接真实检索服务时替换该函数即可，
   断言与探测矩阵无需改动。
3. 会话存储 `_SESSIONS` 是进程内字典，接真实服务时替换为 Redis/DB，接口签名不变。
4. 语料 `corpus/corpus.json` 换成真实文档库导出（保持 `doc_id/title/status/roles/slices/restricted` 字段）。

## 6. 已知边界

- 注入检测是规则+归一化，覆盖 10 类改写句式；对抗性更强的生成式注入需接入模型侧护栏，
  本套件只保证已列出的探测项不泄露。
- 会话计数在进程内，多实例部署时需外部存储才能跨实例一致。
