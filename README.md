# #2052 红队攻击变体生成器：改写、编码绕过与多轮拆分 — 交付包

**运行验证**：`python verify.py`（内部 `pytest tests -q` + `python probe.py`；数字全部由运行结果提取，见 `outputs/verify.json` / `matrix.md`）。

## 最新运行结果
- pytest：**14 passed**（见 `outputs/pytest-output.txt`）。
- 分组矩阵见 `outputs/matrix.md`：AC1 覆盖统计 3、AC2 去重 2、AC3 抽检准入 2、AC4 lint/pii-scan 3、边界 4。

## 结构
| 文件 | 说明 |
|---|---|
| `app/redteam.py` | generate（10 种子 × 6 类 × 2）、6 类技术模板、too_similar 双指标去重、promote 抽检准入、eval_lint / eval_pii_scan |
| `tests/test_2052.py` | 14 个用例，命名 `test_<编号>_<分组>` |
| `verify.py` / `groups.json` | 离线验证器与验收分组配置 |

## 关键实现
- **6 类技术**：synonym_rewrite / roleplay_wrap / encoding_bypass（拼音、全角+零宽字符、base64 输出要求）/ language_switch（英文、中英混杂）/ multi_turn_split（3–4 轮看似无害子问题）/ pressure_wrap；统计输出（每类 = 10 种子 × 2 = 20 条）。
- **溯源继承**：每个变体带 seed_case_key 与 technique，继承种子 forbidden_points / canary / severity（测试断言）。
- **去重**：与种子或其他变体相似度 > 0.9 丢弃（trigram Jaccard + 归一化编辑距离双指标）。
- **抽检准入**：pending 中变体全部 inspected=false 时 promote 抛错且回归集不变；抽检率 ≥10% 后才并入（3/24 = 12.5% 演示通过）。
- **eval-lint**：结构完整性与 technique 白名单校验；**eval-pii-scan**：真实格式手机号/18 位身份证命中即拦，虚构占位（1380000xxxx）不阻断。
- **环境变量**：生成模型地址只从 `REDTEAM_MODEL_BASE_URL` 读取，缺省 fail-fast；被测输出只进复核队列、不直接对外发送，AI 不计算金额。

## 离线口径与对接点
- 本地改写模型离线等价：模板化改写（确定性、可复现）；生产实现把模板替换为对 `REDTEAM_MODEL_BASE_URL` 的本地模型调用（校验域名非境外，接口签名见 README）。
- 目录口径：生成结果写入 `evals/suites/guardrail.variants.pending/`（测试演示以 pending.json 落盘），promote 后并入回归集；与 EVAL-025~028 的种子/回归集通过 seed_case_key 对接。
- 依赖：仅 Python 3.11+ 标准库 + pytest；全部内容虚构。

## 交付包获取方式（git bundle，可复跑）

本单代码以 **git bundle** 形式交付（返工意见认可的交付形式 ②）。该文件是一个完整 git 仓库的单文件快照，可离线克隆并复跑全部测试。

```bash
# 1) 下载（公开链接，无需登录）
curl -L -o pkg.bundle "https://clawhunt-relay.app.workbuddy.host/2052/pkg.bundle?sharecode=R24KOKETNU"

# 2) 校验（SHA-256 见交付正文「交付形式」一节）
sha256sum pkg.bundle
# Windows: certutil -hashfile pkg.bundle SHA256

# 3) 克隆并复跑
git clone pkg.bundle pkg && cd pkg
pip install pytest
python -m pytest tests -q        # 期望：14 passed
python tools/evidence_2052.py    # 期望：variants=120 tech=6/6 lint_pass=120/120 pii_pass=120/120
python verify.py                 # 期望：passed=14 failed=0 groups=5，退出码 0
```

仓库内容：`app/redteam.py`（生成器与两条检查器）、`tests/test_2052.py`（14 用例）、
`tools/evidence_2052.py`（证据生成器）、`groups.json`、`verify.py`、
`outputs/`（junit.xml、matrix.md、run-report.md、verify.json、pytest-output.txt、
variants.json、variants-stats.md、eval-lint.txt、eval-pii-scan.txt）、`README.md`。
`outputs/variants.json` 为 10 条种子 × 6 类技术生成的全部 120 条变体（含 seed_case_key 与 technique）。
