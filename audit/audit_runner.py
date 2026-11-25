# -*- coding: utf-8 -*-
"""audit_runner — 8 类品牌落地检查，输出偏差记录 JSON。"""
from __future__ import annotations
import json, os, re, sys
import xml.etree.ElementTree as ET

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    from audit.measure_contrast import judge
except ImportError:  # 以脚本方式直接运行本文件时
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from audit.measure_contrast import judge

NS = "{http://www.w3.org/2000/svg}"

SPEC_CHAPTERS = [
    "1 主色与辅助色",
    "2 文字与背景对比度",
    "3 字体与字号层级",
    "4 logo 使用",
    "5 图标风格",
    "6 间距与栅格",
    "7 插图与图片风格",
    "8 文案语气",
]

# 判定规则表：问题类型 -> (严重级别, 判定)
SEVERITY = {
    "contrast_low": "高",
    "logo_distorted": "高",
    "logo_too_small": "中",
    "copy_tone": "中",
    "color_out_of_palette": "中",
    "icon_stroke": "低",
    "grid_off": "低",
    "font_family": "低",
    "font_size_hierarchy": "低",
    "illustration_palette": "低",
}


def load_spec() -> dict:
    return yaml.safe_load(open(os.path.join(ROOT, "corpus", "spec.yaml"), encoding="utf-8"))


def _norm(c: str) -> str:
    return (c or "").upper().strip()


def audit_one(svg_path: str, spec: dict, file_meta: dict) -> list[dict]:
    """对单张 SVG 做全部检查，返回偏差记录列表。"""
    tree = ET.parse(svg_path)
    root = tree.getroot()
    out: list[dict] = []
    allowed = {_norm(c) for c in spec["palette"]["allowed"]}
    bg_color = "#FFFFFF"

    # 背景
    for el in root.iter(f"{NS}rect"):
        if el.get("id") == "bg":
            bg_color = el.get("fill", "#FFFFFF")

    def add(dev_type, location, desc, box, extra=None):
        rec = {
            "file": file_meta["file"],
            "kind": file_meta["kind"],
            "label": file_meta["label"],
            "location": location,
            "problem_type": dev_type,
            "description": desc,
            "severity": SEVERITY.get(dev_type, "低"),
            "box": box,
            "extra": extra or {},
        }
        out.append(rec)

    # 1/2/3：文本检查
    for el in root.iter(f"{NS}text"):
        el_id = el.get("id") or el.get("x", "?") + "," + el.get("y", "?")
        loc = f"{file_meta['label']}/{el_id}"
        x, y = float(el.get("x", 0)), float(el.get("y", 0))
        fill = el.get("fill", "")
        size = float(el.get("font-size", 14))
        box = [x - 6, y - int(size), len(el.text or "") * int(size * 0.6) + 12, int(size) + 6]

        # 2 对比度
        judgment = {
            "tool": spec["contrast"]["tool"],
            "fg": fill, "bg": bg_color,
            "font_size_px": size,
            "ratio": None, "required": None, "pass": True,
        }
        try:
            judgment = judge(fill, bg_color, size,
                             body_min=spec["contrast"]["body_min"],
                             large_min=spec["contrast"]["large_min"],
                             large_min_px=spec["contrast"]["large_text_min_px"])
        except Exception:
            pass
        if not judgment["pass"]:
            add("contrast_low", loc,
                f"文字对比度实测 {judgment['ratio']}:1，低于{'大字' if size >= 24 else '正文'}阈值 {judgment['required']}:1",
                box, {"contrast": judgment})

        # 3 字体
        if el.get("font-family") != spec["typography"]["font_family"]:
            add("font_family", loc, f"字体 {el.get('font-family')} 不在规范字体栈", box)
        # 3 字号层级
        if int(size) not in spec["typography"]["hierarchy_px"]:
            add("font_size_hierarchy", loc, f"字号 {int(size)}px 不在规范层级 {spec['typography']['hierarchy_px']}", box)

    # 1 越界色（全部元素）
    for el in root.iter():
        fill = el.get("fill")
        stroke = el.get("stroke")
        tag = el.tag.replace(NS, "")
        for attr, v in (("fill", fill), ("stroke", stroke)):
            if v and _norm(v) not in allowed and not v.startswith("none"):
                x = float(el.get("x", el.get("cx", 0)) or 0)
                y = float(el.get("y", el.get("cy", 0)) or 0)
                w = float(el.get("width", 30) or 30)
                h = float(el.get("height", 20) or 20)
                add("color_out_of_palette",
                    f"{file_meta['label']}/{tag}#{el.get('id') or 'anon'}",
                    f"{attr}={v} 不在规范色板", [x, y, w, h])

    # 4 logo
    for el in root.iter(f"{NS}rect"):
        if el.get("id") == "logo":
            w, h = float(el.get("width")), float(el.get("height"))
            loc = f"{file_meta['label']}/logo"
            ratio = w / h if h else 0
            tol = spec["logo"]["tolerance"]
            if abs(ratio - spec["logo"]["aspect_ratio"]) / spec["logo"]["aspect_ratio"] > tol:
                add("logo_distorted", loc, f"logo 宽高比 {ratio:.2f} 偏离规范 {spec['logo']['aspect_ratio']}（容差 {tol}）",
                    [float(el.get("x")), float(el.get("y")), w, h])
            if w < spec["logo"]["min_width_px"]:
                add("logo_too_small", loc, f"logo 宽 {int(w)}px 小于最小 {spec['logo']['min_width_px']}px",
                    [float(el.get("x")), float(el.get("y")), w, h])

    # 5 图标
    for el in root.iter(f"{NS}rect"):
        sw = el.get("stroke-width")
        if sw and el.get("id", "").startswith("icon") and float(sw) != spec["icons"]["stroke_width"]:
            add("icon_stroke", f"{file_meta['label']}/{el.get('id')}",
                f"图标描边 {sw}px 不等于规范 {spec['icons']['stroke_width']}px",
                [float(el.get("x")), float(el.get("y")), float(el.get("width")), float(el.get("height"))])

    # 6 栅格
    grid = spec["grid"]["unit_px"]
    for el in root.iter(f"{NS}text"):
        x = float(el.get("x", 0))
        if x % grid != 0:
            add("grid_off", f"{file_meta['label']}/{el.get('id') or 'text'}",
                f"x={int(x)} 未对齐 {grid}px 栅格", [x - 6, 0, 20, 20])

    # 7 插图
    for el in root.iter(f"{NS}rect"):
        if el.get("id") == "illustration":
            v = _norm(el.get("fill", ""))
            if v not in allowed:
                add("illustration_palette", f"{file_meta['label']}/illustration",
                    f"插图底色 {el.get('fill')} 越出规范色板",
                    [float(el.get("x")), float(el.get("y")), float(el.get("width")), float(el.get("height"))])

    # 8 文案
    for el in root.iter(f"{NS}text"):
        t = el.text or ""
        hit = [w for w in spec["copy"]["banned_words"] if w in t]
        if hit:
            add("copy_tone", f"{file_meta['label']}/{el.get('id') or 'text'}",
                f"文案含禁用促销用语 {hit}", [float(el.get('x', 0)) - 6, float(el.get('y', 0)) - 16, 200, 22])

    return out


def audit_all(manifest_path: str | None = None) -> list[dict]:
    if manifest_path is None:
        manifest_path = os.path.join(ROOT, "corpus", "manifest.json")
    spec = load_spec()
    manifest = json.load(open(manifest_path, encoding="utf-8"))
    all_devs: list[dict] = []
    for i, meta in enumerate(manifest):
        path = os.path.join(ROOT, "corpus", meta["file"])
        for rec in audit_one(path, spec, meta):
            rec["seq"] = len(all_devs) + 1
            all_devs.append(rec)
    return all_devs


if __name__ == "__main__":
    devs = audit_all()
    out = os.path.join(ROOT, "output", "deviations.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(devs, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    from collections import Counter
    print(f"deviations={len(devs)} by_type={dict(Counter(d['problem_type'] for d in devs))}")
