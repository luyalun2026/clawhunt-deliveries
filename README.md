# 评测执行器（EVAL-003）· eval-run

会员空间平台「评测、红队与质量月报」阶段的 AI 工具评测执行器。提供 `eval-run` 命令与 Python API
`run_suite(suite_key, target, options)`，通过适配器调用被测工具的**内部评测入口**，落库 `eval_run` /
`eval_result`，并用退出码供 CI 判断。

## 1. 运行与测试

```bash
# 方式 A：源码直接跑（零第三方依赖，Python 3.11+）
python -m eval_runner.cli run --suite mock20 --target mock --concurrency 4 --db db/eval.sqlite3

# 方式 B：可编辑安装后使用命令
pip install -e ".[dev]"
eval-run run --suite mock20 --target mock --concurrency 1

# 测试（8 个用例，含 4 条 AC 逐条断言）
python -m pytest -q -s
```

Python API：

```python
from eval_runner import run_suite, build_adapter
import json

cfg = json.load(open("config/tools.json", encoding="utf-8"))
adapter = build_adapter(cfg, "kb_assistant")
summary = run_suite("mock20", "kb_assistant", options={
    "concurrency": 4,          # 并发度，默认 4
    "timeout_s": 60,           # 单用例超时，默认 60 秒
    "retries": 1,              # 失败/超时重试 1 次
    "tags": ["smoke"],         # --tags
    "case_ids": [],            # --case
    "sample": 50, "seed": 42,  # --sample N 固定种子抽样，同样本可复现
    "pass_threshold": 0.8,     # 通过率阈值
    "resume_run_id": None,     # --resume <run_id>
    "db_path": "db/eval.sqlite3",
}, adapter=adapter)
print(summary.exit_code, summary.pass_rate)
```

## 2. 退出码（供 CI 判断）

| 退出码 | 含义 | 判定优先级 |
|---|---|---|
| `0` | 全部用例执行完成且通过率 ≥ `pass_threshold` | — |
| `2` | 有用例执行错误（含超时重试 1 次后仍失败） | 最高：只要存在 error 即为 2 |
| `3` | 无执行错误，但通过率 < `pass_threshold` | 次之 |

`passed` / `failed` 的区别：`failed` 是被测服务正常返回但断言不成立（评测结论为不达标），不算执行错误；
`error` 是超时、网络或协议错误（评测本身没跑通），会使整体退出码为 2。

## 3. 适配器

| 适配器 | 说明 |
|---|---|
| `HttpAdapter` | `POST {base_url}/internal/eval/{tool}/invoke`，请求体固定 `eval_mode=true`、`case_id`、`input`、`expected`。评测模式下被测服务不得写入真实复核队列、不得触发任何对外发送。鉴权 token **只从环境变量读取**（配置里只写变量名 `token_env`）。 |
| `EchoMockAdapter` | 离线 mock，行为由用例 `input.behavior`（`ok`/`fail`/`timeout`）与 `input.sleep` 决定，用于自测与 CI。 |
| `stub` | 被测工具接口未就绪时的桩（`config/tools.json` 中 `site_qa` 当前为 `stub`，对接点已在配置的 `stub_reason` 写明）。 |

7 个 AI 工具的入口地址与鉴权配置见 `config/tools.json`；密钥一律走环境变量
`EVAL_KB_ASSISTANT_TOKEN` 等，**配置文件中不含任何明文密钥**。

## 4. 数据模型

`schema.sql` 为 PostgreSQL 16 的生产 DDL；`eval_runner/store.py` 是字段与语义一致的 SQLite 同构实现
（本地与 CI 免依赖）。两表均含统一字段 `id(UUID) / org_id / site_id / created_at / created_by /
updated_at / deleted_at`，`eval_result` 上有 `UNIQUE (run_id, case_id)` —— 这是「续跑不产生重复结果行」的
硬约束（AC3）。

## 5. 验收标准对照

| # | 验收标准 | 实现位置 | 测试 | 实测 |
|---|---|---|---|---|
| 1 | 20 条 mock 用例、`--concurrency 4` 总耗时约为串行 1/4 | `core.run_suite` 线程池 | `tests/test_ac.py::test_ac1_concurrency_speedup_is_about_4x` | 串行 1021 ms vs 并发 272 ms → **3.75×** |
| 2 | 模拟超时用例重试 1 次后记为 error，退出码 2 | `core._execute_case` 重试循环 | `tests/test_ac.py::test_ac2_timeout_retry_once_then_error_exit_2` | `SLOW-01` status=error、attempts=**2**、exit_code=**2** |
| 3 | 中途中断后 `--resume` 只执行剩余用例，结果表无重复 | `store.completed_case_ids` + `run_suite` 续跑分支 | `tests/test_ac.py::test_ac3_resume_runs_only_remaining_cases` | 首轮 8 → 续跑执行 **12**、跳过 8、结果行 **20**、去重 20、第二轮仅调用 12 条 |
| 4 | 通过率低于阈值时退出码 3 | `run_suite` 退出码判定 | `tests/test_ac.py::test_ac4_below_threshold_exit_3` | 10 条中 5 过 → pass_rate **0.50**、error 0、exit_code **3** |

实测原始输出见 `outputs/pytest.txt`（pytest 全量输出）、`outputs/cli-run.txt`（CLI 冒烟）、
`outputs/verify.json`（机器可读校验结果）、`outputs/ac-checklist.csv`（AC 逐条对照表）。

## 6. 工程约定落实

- 金额：本单无金额计算；表结构未引入任何浮点金额列（如需扩展，一律「分」存整数）。
- 配置与密钥只从环境变量读取；`config/tools.json` 仅存入口地址与变量名。
- 业务表统一含 `id/org_id/site_id/created_at/created_by/updated_at/deleted_at`（软删除）。
- 不引入任何向境外发送数据的第三方 SDK；全部依赖为 Python 标准库（测试仅需 pytest）。
- 依赖其他工单（EVAL-004 / EVAL-005 评分器）时为桩：评分调用点写在 `core.run_suite` 的
  `judge` 钩子（`BaseAdapter.judge`），README 即对接点说明。
- 只用虚构测试数据，交付物不含客户名称与任何真实个人信息。
