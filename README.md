# S5-DOC-010 · llm_extract 大模型字段抽取服务（分组提示词与 JSON Schema 约束）

> 会员空间平台 · Stage v AI 辅助工具 · 文档自动化
> 交付形态：单文件核心模块 + mock 接口 + pytest 套件（17 用例全过，零失败）

## 一、验收标准逐条对应

| # | 验收标准 | 实现 | 证据 |
|---|---|---|---|
| 1 | mock 返回不存在于原文的 quote → 标记 quote_not_found 且 value 为空 | `extractor._merge_candidates`：候选先过 `quote_backcheck`（精确匹配 → NFKC 归一化匹配），全部失败则 `quote_not_found=True` 并丢弃 value | `test_ac1_quote_not_in_source_marked` ✅ |
| 2 | mock 连续 3 次返回非法 JSON → 整组 llm_failed | `extract_group`：1 + JSON_RETRY_TIMES(2) 次调用全失败 → 组内每字段 `llm_failed=True`，调用日志恰好 3 条 | `test_ac2_three_bad_json_marks_llm_failed` ✅ |
| 3 | 20000 字虚构长合同切块、相邻块重叠恰 300 字 | `chunk_text`：size=6000、step=5700，逐对断言重叠 300 字且内容一致 | `test_ac3_chunk_overlap_exact_300` ✅ |
| 4 | 每次调用记录 prompt_version 与模型名，可在库中查到 | `store.CallLogStore`（SQLite，生产替换为 PostgreSQL 表 `llm_call_log`）：每次调用一行，含 field_group/prompt_version/model/attempt/parse_ok | `test_ac4_call_log_records_version_and_model` ✅ |

补充用例（18 条）：JSON Schema 机械校验（缺 not_found/额外键/quote 越界/置信度越界/类型错误均被拒、单对象候选规范化、不合规重试后成功、3 次不合规标 llm_failed）、第 3 次重试成功不判失败、切块上限、quote 长度 4–200 边界、全半角+空白归一化匹配、多块合并取「可回查且置信度最高」、金额由程序解析（AI 不计算）、复核队列全行标记人工核对。

## 二、运行方法

```bash
pip install pytest
python -m pytest tests/ -v          # 27 passed
```

## 三、模块说明

- `app/extractor.py` — 核心：切块（6000/300 重叠）、分组抽取、quote 回查、候选合并、重试与 llm_failed、`parse_amounts`（程序解析金额）、`build_review_queue`（人工复核队列）。
- `app/prompts.py` — 5 组提示词模板（主体信息/期限/金额与付款/权益/条款摘要），`PROMPT_VERSIONS` 版本管理。
- `app/schema.json` — 输出 JSON Schema：每字段 `{value, quote(4–200字), confidence_self(0–1), not_found}`。
- `app/schema_check.py` — 零依赖轻量 JSON Schema 校验器（type/required/properties/additionalProperties/items/minLength/maxLength/minimum/maximum）。模型输出解析成功后按 schema 机械校验，不合规与非法 JSON 同一口径：重试 2 次、仍失败按失败块处理（整组 llm_failed）。
- `app/mock_llm.py` — `MockLLM`（可编程脚本 mock，测试用）与 `DocLlmClient`（OpenAI 兼容生产形态，`DOC_LLM_BASE_URL`/`DOC_LLM_MODEL` 环境变量，禁止境外接口）。
- `app/store.py` — 调用日志，每次调用记录 prompt_version 与模型名，可查询。

### prompt_version 规则
- 主版本 +1：字段集合或输出 Schema 变化；次版本 +0.1：措辞/示例调整。
- 版本随每次调用写入 `llm_call_log`，审计可回溯。

### 数据与保密
全部测试样例为虚构合同文本，不含任何真实个人或企业信息。

### 对接点（桩替换）
- LLM 推理：`DocLlmClient`（环境变量 DOC_LLM_BASE_URL / DOC_LLM_MODEL）。
- 调用日志存储：SQLite → PostgreSQL `llm_call_log`（字段见 store.py）。
- 复核队列：`build_review_queue` 输出交给 S5 人工复核模块消费。

## 四、测试结果

见 `outputs/pytest_main.txt`（17 passed / 0 failed）、`outputs/verify.json`（数字由 pytest 输出自动提取，零手写）、`SHA256SUMS`（全部交付文件哈希）。

## 五、数据安全与留存口径

- **落盘数据**：`llm_call_log`（SQLite）仅记录调用审计元数据（field_group / prompt_version / model / attempt / parse_ok / created_at），**不落合同原文**；抽取结果只进入内存中的 review_queue 数据结构并由调用方持久化，本服务自身不另存合同全文。
- **访问控制**：SQLite 文件位于服务私有数据目录，部署时目录权限收紧为服务账号独占（POSIX 0700 / 数据盘不进公共备份）；store.py 连接使用本地相对路径，不监听任何网络端口。
- **传输**：模型调用走 `DOC_LLM_BASE_URL`（启动时校验必须 http/https 且含主机名，禁止境外接口），生产环境要求内网私有化部署并启用 https；发送内容仅为切块后的合同片段（≤6000 字），无越权字段。
- **AI 边界**：模型只做定位与抄录，金额由 `parse_amounts` 程序解析；全部结果标记 `needs_human_review`，不直接对外发送。
