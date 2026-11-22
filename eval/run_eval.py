# -*- coding: utf-8 -*-
"""截止日期抽取评测：对虚构评测集逐篇抽取，与构造标签比对，输出准确率。

判定口径：抽取出的 (deadline_type, deadline) 集合与标签集合完全一致的文档
才计为该篇 deadline 正确；准确率 = 正确文档数 / 总文档数。
另输出逐条 recall（标签条目被召回的比例）与逐篇明细。
运行：python eval/run_eval.py
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.extractor import extract  # noqa: E402


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "eval_set.json"), encoding="utf-8") as f:
        data = json.load(f)

    detail = []
    doc_correct = 0
    total_labels = 0
    recalled_labels = 0
    for doc in data["docs"]:
        pub = datetime.strptime(doc["publish_date"], "%Y-%m-%d")
        out = extract(doc["text"], pub)
        got = {(x["deadline_type"], x["deadline"]) for x in out["deadlines"]}
        want = {(x["deadline_type"], x["deadline"]) for x in doc["expected_deadlines"]}
        earliest = out["earliest_submission"]
        earliest_ok = earliest == doc["expected_earliest_submission"]
        ok = got == want and earliest_ok
        doc_correct += ok
        total_labels += len(want)
        recalled_labels += len(got & want)
        detail.append({"id": doc["id"], "ok": ok,
                       "got": sorted(got), "want": sorted(want),
                       "earliest_got": earliest,
                       "earliest_want": doc["expected_earliest_submission"],
                       "dropped": len(out["audit"]["dropped"])})

    accuracy = doc_correct / len(data["docs"])
    recall = recalled_labels / total_labels if total_labels else 0.0
    result = {"docs": len(data["docs"]), "doc_correct": doc_correct,
              "accuracy": round(accuracy, 4), "label_recall": round(recall, 4),
              "threshold": 0.90, "pass": accuracy >= 0.90, "detail": detail}
    out_path = os.path.join(here, "eval_result.json")
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in result.items() if k != "detail"}, ensure_ascii=False))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
