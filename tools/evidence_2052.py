# -*- coding: utf-8 -*-
"""#2052 证据生成器：产出「变体集 / eval-lint / eval-pii-scan」三类可核对产物。

对应返工意见第 2、5 条（AC1 变体集与统计输出、AC4 两条检查命令的实际输出）。
数字全部由本次运行实时统计，不手写。

用法（在本目录下）：python tools/evidence_2052.py
产出：
  outputs/variants.json        10 条种子生成的全部变体（含 seed_case_key / technique）
  outputs/variants-stats.md    6 类技术覆盖统计与逐类计数
  outputs/eval-lint.txt        eval_lint 对每个变体的逐条结果 + 通过/失败计数
  outputs/eval-pii-scan.txt    eval_pii_scan 对每个变体的逐条结果 + 命中计数
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from app.redteam import TECHNIQUES, eval_lint, eval_pii_scan, generate, load_seeds  # noqa: E402

OUT = os.path.join(HERE, "outputs")


def main():
    os.makedirs(OUT, exist_ok=True)
    seeds = load_seeds()
    variants = generate(seeds)

    with open(os.path.join(OUT, "variants.json"), "w", encoding="utf-8") as f:
        json.dump({"seed_count": len(seeds), "variant_count": len(variants),
                   "seeds": seeds, "variants": variants}, f, ensure_ascii=False, indent=2)

    # 逐类覆盖统计
    per = {}
    for v in variants:
        per[v["technique"]] = per.get(v["technique"], 0) + 1
    lines = ["# 变体集统计（本次运行实时统计）", "",
             "- 种子数：%d" % len(seeds),
             "- 变体数：%d" % len(variants),
             "- 技术类别数：%d / %d" % (len(per), len(TECHNIQUES)), "",
             "| 技术类别 | 变体数 |", "|---|---|"]
    for t in TECHNIQUES:
        lines.append("| %s | %d |" % (t, per.get(t, 0)))
    missing = [t for t in TECHNIQUES if not per.get(t)]
    lines += ["", "- 缺失类别：%s" % ("无" if not missing else "、".join(missing)),
              "- 全部变体带 seed_case_key 与 technique：%s" % (
                  "是" if all(v.get("seed_case_key") and v.get("technique") for v in variants) else "否")]
    with open(os.path.join(OUT, "variants-stats.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    # eval-lint 逐条
    lint_rows, lint_ok = [], 0
    for i, v in enumerate(variants, 1):
        ok, msg = eval_lint(v)
        lint_ok += 1 if ok else 0
        lint_rows.append("%03d %-16s %-8s %s" % (i, v["technique"], "PASS" if ok else "FAIL", msg))
    with open(os.path.join(OUT, "eval-lint.txt"), "w", encoding="utf-8") as f:
        f.write("$ python tools/evidence_2052.py  # eval_lint 逐条\n")
        f.write("\n".join(lint_rows) + "\n")
        f.write("\n被检查变体数：%d｜通过：%d｜失败：%d\n" % (len(variants), lint_ok, len(variants) - lint_ok))

    # eval-pii-scan 逐条
    pii_rows, pii_ok, phone_hits, id_hits = [], 0, 0, 0
    for i, v in enumerate(variants, 1):
        ok, hits = eval_pii_scan(v["variant_prompt"])
        pii_ok += 1 if ok else 0
        phone_hits += hits["phone_hits"]
        id_hits += hits["id_hits"]
        pii_rows.append("%03d %-16s %-8s phone_hits=%d id_hits=%d"
                        % (i, v["technique"], "PASS" if ok else "FAIL",
                           hits["phone_hits"], hits["id_hits"]))
    with open(os.path.join(OUT, "eval-pii-scan.txt"), "w", encoding="utf-8") as f:
        f.write("$ python tools/evidence_2052.py  # eval_pii_scan 逐条\n")
        f.write("\n".join(pii_rows) + "\n")
        f.write("\n被检查变体数：%d｜通过：%d｜失败：%d｜真实格式手机号命中合计：%d｜18 位身份证命中合计：%d\n"
                % (len(variants), pii_ok, len(variants) - pii_ok, phone_hits, id_hits))

    print("variants=%d tech=%d/%d lint_pass=%d/%d pii_pass=%d/%d"
          % (len(variants), len(per), len(TECHNIQUES), lint_ok, len(variants), pii_ok, len(variants)))


if __name__ == "__main__":
    main()
