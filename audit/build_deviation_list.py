#!/usr/bin/env python3
"""build_deviation_list.py — 偏差清单 Excel + 判定（执行偏差 / 规范缺失）+ 摘要报告。"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from audit.annotate import annotate_all
from audit.audit_runner import SPEC_CHAPTERS, audit_all

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

# 规范是否覆盖该问题类型（用于执行偏差 / 规范缺失判定）
SPEC_COVERED = {
    "contrast_low": True,       # 规范有 AA 阈值 -> 没做到 = 执行偏差
    "color_out_of_palette": True,
    "font_family": True,
    "font_size_hierarchy": True,
    "logo_distorted": True,
    "logo_too_small": True,
    "icon_stroke": True,
    "grid_off": True,           # 规范有 8px 栅格约定 -> 执行偏差
    "illustration_palette": True,
    "copy_tone": True,          # 规范有禁用词表 -> 执行偏差
}

TYPE_TO_CHAPTER = {
    "color_out_of_palette": SPEC_CHAPTERS[0],
    "contrast_low": SPEC_CHAPTERS[1],
    "font_family": SPEC_CHAPTERS[2],
    "font_size_hierarchy": SPEC_CHAPTERS[2],
    "logo_distorted": SPEC_CHAPTERS[3],
    "logo_too_small": SPEC_CHAPTERS[3],
    "icon_stroke": SPEC_CHAPTERS[4],
    "grid_off": SPEC_CHAPTERS[5],
    "illustration_palette": SPEC_CHAPTERS[6],
    "copy_tone": SPEC_CHAPTERS[7],
}


def classify(dev: dict) -> str:
    return "执行偏差" if SPEC_COVERED.get(dev["problem_type"], False) else "规范缺失"


def build(devs: list[dict], out_dir: str) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    corpus_root = os.path.join(ROOT, "corpus")
    annotated = annotate_all(devs, corpus_root, os.path.join(out_dir, "annotated"))

    wb = Workbook()
    ws = wb.active
    ws.title = "偏差清单"
    headers = ["编号", "文件", "页面类型", "位置", "问题类型", "偏差描述", "严重级别",
               "频次(同类累计)", "判定", "规范章节", "对比度实测", "测量工具", "标注文件"]
    widths = [6, 26, 10, 30, 22, 46, 10, 12, 10, 16, 22, 34, 34]
    hf = Font(bold=True)
    fill = PatternFill("solid", fgColor="EEF2F7")
    for c, (h, w) in enumerate(zip(headers, widths), 1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.font = hf
        cell.fill = fill
        ws.column_dimensions[get_column_letter(c)].width = w

    type_count: dict[str, int] = {}
    for d in devs:
        type_count[d["problem_type"]] = type_count.get(d["problem_type"], 0) + 1

    r = 2
    for d in devs:
        contrast = d["extra"].get("contrast") or {}
        annot_rel = os.path.relpath(annotated[d["file"]], out_dir)
        row = [
            d["seq"], d["file"], d["kind"], d["location"], d["problem_type"],
            d["description"], d["severity"], type_count[d["problem_type"]],
            classify(d), TYPE_TO_CHAPTER[d["problem_type"]],
            (f"{contrast['ratio']}:1 (要求 {contrast['required']}:1)" if contrast else "—"),
            contrast.get("tool", "—"),
            annot_rel,
        ]
        for c, v in enumerate(row, 1):
            ws.cell(row=r, column=c, value=v)
        r += 1
    xlsx = os.path.join(out_dir, "deviation_list.xlsx")
    wb.save(xlsx)

    # 摘要 JSON（供落地页数字自动提取）
    summary = {
        "total_files": len({d["file"] for d in devs}),
        "total_deviations": len(devs),
        "by_type": type_count,
        "by_severity": {s: sum(1 for d in devs if d["severity"] == s) for s in ("高", "中", "低")},
        "by_judgment": {j: sum(1 for d in devs if classify(d) == j) for j in ("执行偏差", "规范缺失")},
        "annotated_files": len(annotated),
    }
    json.dump(summary, open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(devs, open(os.path.join(out_dir, "deviations.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return summary


if __name__ == "__main__":
    devs = audit_all()
    s = build(devs, os.path.join(ROOT, "output"))
    print(json.dumps(s, ensure_ascii=False))
