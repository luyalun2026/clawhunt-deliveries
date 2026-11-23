# #2052 红队攻击变体生成器：改写、编码绕过与多轮拆分 — 交付包（v3）

**运行验证**：`python verify.py`（内部 `pytest tests -q`，指标在本进程内实测；数字见 `outputs/verify.json` / `matrix.md`）。

## 最新运行结果

- pytest：**20 passed / 0 failed**（`outputs/pytest-output.txt`）。
- 变体集：10 种子 → 候选 150 条，**跨种子全局去重后保留 133 条**，丢弃 17 条；6 类技术全覆盖，每个种子 6 类齐全，**批内 >0.9 的重复对为 0**。
- eval-lint：133/133 通过；eval-pii-scan：133/133 通过（无真实格式手机号/身份证）。

## 命令行入口（本单要求）

```bash
python redteam-gen generate --seeds 10 --root .   # 生成 → evals/suites/guardrail.variants.pending/pending.json
python redteam-gen promote  --root .              # 抽检率 >=10% 才并入 evals/suites/guardrail.regression.json
```

- `generate` 输出：种子数、候选/保留/丢弃条数、逐类计数、pending 相对路径（JSON）。
- `promote` 从 **pending 目录**读取（不是内存变量），未达抽检率时退出码 1 且保持回归集不变。
- 也提供等价的 `redteam-gen.py` 调用方式。

## 结构

| 文件 | 说明 |
|---|---|
| `app/redteam.py` | 六类技术生成、全局去重、编码子类、本地模型改写、pending/promote、eval_lint / eval_pii_scan |
| `app/redteam_cli.py` | `redteam-gen` 子命令实现（generate / promote） |
| `redteam-gen` / `redteam-gen.py` | 命令行入口 |
| `tests/test_2052.py` | 20 个用例（覆盖、去重正反例、跨种子、CLI、模型 mock、编码子类、lint/pii） |
| `verify.py` / `groups.json` | 离线验证器与验收分组配置 |
| `evals/suites/guardrail.variants.pending/pending.json` | 生成结果落盘位置（promote 的输入） |

## 关键实现与口径

- **六类技术**：synonym_rewrite（优先本地模型）/ roleplay_wrap / encoding_bypass / language_switch / multi_turn_split（3 轮）/ pressure_wrap。
- **编码绕过 5 个子类，均基于种子内容**：拼音（逐字转写，未收录字保留原字）、谐音（系统→系桶、提示词→提式词、价格→价各、折扣→折口等）、全角、插入零宽字符、要求 base64 输出（base64 内容即种子原文）。
- **相似度口径（明确说明）**：字符 trigram Jaccard **或** 归一化编辑距离，**任一 > 0.9 即判过近并丢弃**。
- **去重范围**：与全部种子 + **整批已保留变体（含跨种子）** 比较；`generate(seeds, existing=...)` 时 existing（回归集）同样参与比较。
  因此两条完全相同的种子只会产出第一份变体，第二批全部丢弃（`test_06` 断言）。
- **本地模型改写**：`rewrite_synonym()` 优先调用 `REDTEAM_MODEL_BASE_URL` 的 `/v1/chat/completions`（OpenAI 兼容，可注入 mock），异常时回落模板「换种说法：…」，保证流程不中断。
- **地址白名单（默认拒绝）**：仅放行 `localhost/127.0.0.1/::1`、私有网段（10/172.16-31/192.168）、以及 `.local/.internal/.svc/.example/.lan/.cn` 后缀；`.com/.io/.ai/.net/.org` 与公网 IP 一律拒绝，缺省 fail-fast。
- **抽检准入**：pending 全为 `inspected=false` 时 promote 抛错且回归集不变；抽检率 ≥10%（向上取整）才写入回归集。
- **eval-lint**：结构完整性与 technique 白名单；**eval-pii-scan**：真实格式手机号 / 18 位身份证命中即拦，虚构占位（1380000xxxx）不阻断。
- 依赖：Python 3.11+ 标准库 + pytest；全部内容虚构，不出现真实企业与个人信息。

## 交付形式

代码以 **公开 GitHub 仓库分支** 交付（免登录 clone），可另生成 git bundle：

```bash
git clone --branch 2052 https://github.com/luyalun2026/clawhunt-deliveries.git ch2052
cd ch2052
pip install pytest
python -m pytest tests -q        # 期望 20 passed
python tools/evidence_2052.py    # 期望 variants=133 tech=6/6 lint_pass=133/133 pii_pass=133/133
python verify.py                 # 期望 passed=20 failed=0
```

- 仓库分支：`2052`，本次交付 commit 见交付正文；`SHA256SUMS` 列出全部受版本管理文件的 SHA-256。
- 离线包：克隆后 `git bundle create 2052.bundle --all` 即可生成同内容 bundle。
- `outputs/variants.json` 为本次运行生成的 133 条变体（含 seed_case_key 与 technique）及 10 条种子。
