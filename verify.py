# -*- coding: utf-8 -*-
"""一键复现（供审核方验证）：python verify.py

流程：
  1. 运行主测试套件 tests/（必须全部通过）
  2. 运行负向套件 tests_negative/（预期失败，失败输出即 AC #2/#3 证据）
  3. 统计扫描规模（接口数 / 身份数 / 请求数）
  4. 生成 outputs/report.md 与 SHA256SUMS
所有数字均由实际运行结果自动提取，无手写值。
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PKG = Path(__file__).resolve().parent
OUT = PKG / "outputs"
OUT.mkdir(exist_ok=True)

PY = sys.executable


def run(cmd: list[str], capture: Path) -> subprocess.CompletedProcess:
    p = subprocess.run(cmd, cwd=PKG, capture_output=True, text=True, encoding="utf-8", errors="replace")
    capture.write_text((p.stdout or "") + (p.stderr or ""), encoding="utf-8")
    return p


print("[1/4] 运行主测试套件 tests/ ...")
p_main = run([PY, "-m", "pytest", "tests", "-v", "--tb=short", "-s"], OUT / "pytest_main.txt")
print(f"      exit={p_main.returncode}（要求 0）")
if p_main.returncode != 0:
    print(p_main.stdout[-3000:])
    sys.exit("主套件未全部通过，终止")

# 从主套件输出末尾摘要行提取统计（如 "22 passed, 1 warning in 3.55s"）
main_txt = (OUT / "pytest_main.txt").read_text(encoding="utf-8")
m_pass = re.search(r"(\d+) passed", main_txt)
m_fail = re.search(r"(\d+) failed", main_txt)
n_passed = int(m_pass.group(1)) if m_pass else 0
n_failed_main = int(m_fail.group(1)) if m_fail else 0

print("[2/4] 运行负向套件 tests_negative/（预期失败）...")
p_neg = run([PY, "-m", "pytest", "tests_negative", "-v", "--tb=long"], OUT / "pytest_negative_expected_fail.txt")
print(f"      exit={p_neg.returncode}（要求非 0：负向用例必须失败才证明断言有效）")
if p_neg.returncode == 0:
    sys.exit("负向用例竟然全部通过 → 断言无效，终止")

neg_txt = (OUT / "pytest_negative_expected_fail.txt").read_text(encoding="utf-8")
m_negfail = re.search(r"(\d+) failed", neg_txt)
neg_fail_n = int(m_negfail.group(1)) if m_negfail else 0

print("[3/4] 统计扫描规模 ...")
sys.path.insert(0, str(PKG))
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.seed import all_canary_values  # noqa: E402
from tests.scan_helper import IDENTITIES, iter_requests, list_mini_get_endpoints  # noqa: E402

client = TestClient(app)
eps = list_mini_get_endpoints(client)
req_count = sum(1 for ep in eps for _ in iter_requests(client, ep))
canary_n = len(all_canary_values())

print("[4/4] 生成 report.md 与 SHA256SUMS ...")
lines = [
    "# S3-MINI-045 脱敏自动化测试 · 运行报告",
    "",
    f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    f"- Python：{sys.version.split()[0]} / FastAPI + httpx TestClient",
    "",
    "## 扫描规模（AC #1）",
    f"- OpenAPI 枚举到的 /api/mini/ GET 接口数：**{len(eps)}**",
    f"- 身份数：**{len(IDENTITIES)}**（{', '.join(IDENTITIES)}）",
    f"- 接口 × 身份 × 路径填充 的请求总数：**{req_count}**",
    f"- 每个响应递归检查：金丝雀值（{canary_n} 个）× 禁键 7 种 × 手机号/邮箱/座机正则",
    "",
    "## 结果",
    f"- 主套件：**{n_passed} passed，{n_failed_main} failed**（outputs/pytest_main.txt）",
    f"- 负向套件：**{neg_fail_n} 个用例按预期失败**（outputs/pytest_negative_expected_fail.txt）",
    "",
    "## 被扫描接口清单",
]
for e in eps:
    lines.append(f"- `{e['path']}`（路径参数 {e['params'] or '无'}，查询参数 {e['query'] or '无'}）")

lines += [
    "",
    "## 负向证据（AC #2 / AC #3）",
    "破坏版应用（app/broken_app.py）注入 phone 禁键与高精度坐标，同一套断言必须拦截。",
    f"负向套件运行结果：{neg_fail_n} 个用例 FAILED（完整输出见 outputs/pytest_negative_expected_fail.txt）。",
]

# 失败输出节选（证明断言真的抛了 AssertionError）
excerpt = []
for m in re.finditer(r"(AssertionError: 联系方式脱敏校验失败[\s\S]{0,400}|AssertionError: 街道级坐标校验失败[\s\S]{0,400})", neg_txt):
    excerpt.append(m.group(0))
lines += ["", "### 失败输出节选", "```text"]
for ex in excerpt[:6]:
    lines.append(ex.strip()[:500])
    lines.append("----")
lines.append("```")
lines += [
    "",
    "## 复现方式",
    "```bash",
    "pip install fastapi httpx pytest",
    "python verify.py   # 一键复现：主套件必须全过，负向套件必须失败",
    "pytest tests -v    # 仅跑主套件（CI 同款）",
    "```",
]

(OUT / "report.md").write_text("\n".join(lines), encoding="utf-8")

# SHA256SUMS（按固定顺序：源码与配置，排除 outputs 与缓存）
files = sorted(
    [p for p in PKG.rglob("*") if p.is_file()
     and "outputs" not in p.parts and ".pytest_cache" not in p.parts
     and "__pycache__" not in p.parts and p.name not in ("SHA256SUMS",)]
)
with (PKG / "SHA256SUMS").open("w", encoding="utf-8", newline="\n") as fh:
    for p in files:
        rel = p.relative_to(PKG).as_posix()
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        fh.write(f"{h}  {rel}\n")

summary = {
    "endpoint_count": len(eps),
    "identity_count": len(IDENTITIES),
    "request_count": req_count,
    "canary_count": canary_n,
    "main_passed": n_passed,
    "main_failed": n_failed_main,
    "negative_failed": neg_fail_n,
    "exit": 0,
}
(OUT / "verify.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
print("完成：", json.dumps(summary, ensure_ascii=False))
