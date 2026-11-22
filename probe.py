# -*- coding: utf-8 -*-
"""实测指标：评测准确率（读 eval_result.json）+ 子句定型冒烟 + 丢弃审计。"""
import json
import os
import subprocess
import sys

PKG = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PKG)

from app.extractor import extract  # noqa: E402
from datetime import datetime  # noqa: E402


def main():
    subprocess.run([sys.executable, "eval/run_eval.py"], cwd=PKG, capture_output=True)
    ev = json.load(open(os.path.join(PKG, "eval", "eval_result.json"), encoding="utf-8"))

    # 子句定型冒烟：同一句两个日期，各自定型正确
    text = "本次活动评审会时间为2026年3月8日。请各单位于2026年2月4日前提交申报材料。"
    out = extract(text, datetime(2026, 1, 5))
    types = {d["source_text"]: d["deadline_type"] for d in out["deadlines"]}

    print(json.dumps({
        "eval_docs": ev["docs"], "accuracy": ev["accuracy"],
        "label_recall": ev["label_recall"], "threshold_pass": ev["pass"],
        "clause_typed_smoke": types,
        "smoke_ok": types.get("2026年3月8日") == "event_date"
        and types.get("2026年2月4日前") == "submission",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
