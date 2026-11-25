#!/usr/bin/env python3
"""build_revision_suggestions.py — 按规范章节归类修订建议，每条回链偏差编号。"""
from __future__ import annotations
import json, os, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from audit.audit_runner import SPEC_CHAPTERS

SUGGESTION = {
    "contrast_low": "对低对比度文本统一替换为 neutral_text 色（#1F2937）或按大字/正文阈值重新选色；建议在工作台设计 tokens 中固化 AA 达标色对。",
    "color_out_of_palette": "在组件库层面收敛色板：仅暴露规范色板 token，移除硬编码色值；CI 增加 SVG/样式色值扫描。",
    "font_family": "全局替换为规范字体栈，并在前端构建配置中做字体白名单。",
    "font_size_hierarchy": "字号收敛到规范层级集合，删除越界字号；设计 tokens 增加字号枚举校验。",
    "logo_distorted": "为 logo 提供固定宽高比的组件（Logo 组件），禁止手工拉伸；布局中锁定 aspect-ratio。",
    "logo_too_small": "规定 logo 最小宽度 {min}px，小于该尺寸场景改用简化版标识。",
    "icon_stroke": "图标统一 {stroke}px 描边，图标库按统一笔画宽度重新导出。",
    "grid_off": "布局间距对齐 {grid}px 栅格；在样式 lint 中增加栅格对齐检查。",
    "illustration_palette": "插图底色限用规范色板；新插图入库前做色板校验。",
    "copy_tone": "在文案规范中固化禁用词表，上线前跑文案扫描脚本。",
}

PARAM = {
    "logo_too_small": ("{min}", "logo.min_width_px"),
    "icon_stroke": ("{stroke}", "icons.stroke_width"),
    "grid_off": ("{grid}", "grid.unit_px"),
}


def main() -> int:
    import yaml
    spec = yaml.safe_load(open(os.path.join(ROOT, "corpus", "spec.yaml"), encoding="utf-8"))
    devs = json.load(open(os.path.join(ROOT, "output", "deviations.json"), encoding="utf-8"))
    from audit.build_deviation_list import TYPE_TO_CHAPTER

    by_chapter: dict[str, list] = defaultdict(list)
    for d in devs:
        by_chapter[TYPE_TO_CHAPTER[d["problem_type"]]].append(d)

    lines = ["# 品牌规范修订建议（按章节归类）", "",
             f"输入：{len(devs)} 条偏差记录，覆盖 {len({d['file'] for d in devs})} 张界面/物料。", "",
             "每条建议注明对应偏差记录编号（#n）。", ""]
    for ch in SPEC_CHAPTERS:
        ds = by_chapter.get(ch, [])
        lines.append(f"## {ch}")
        if not ds:
            lines.append("")
            lines.append("未发现偏差，无需修订。")
            lines.append("")
            continue
        type_ids = defaultdict(list)
        for d in ds:
            type_ids[d["problem_type"]].append(d["seq"])
        lines.append("")
        for ptype, ids in type_ids.items():
            tpl = SUGGESTION.get(ptype, "规范条文需补充可执行的检查口径。")
            for key, (holder, spec_path) in PARAM.items():
                if key == ptype:
                    section, field = spec_path.split(".")
                    tpl = tpl.replace(holder, str(spec[section][field]))
            lines.append(f"- **{ptype}**（偏差 #{', #'.join(map(str, ids))}）：{tpl}")
        lines.append("")

    out = os.path.join(ROOT, "output", "revision_suggestions.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
    print(f"revision_suggestions.md written, chapters={len(by_chapter)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
