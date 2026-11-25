# -*- coding: utf-8 -*-
"""annotate — 在 SVG 副本上叠加红框与编号徽标（每张源图一份标注副本）。"""
from __future__ import annotations
import json, os
import xml.etree.ElementTree as ET

NS = "{http://www.w3.org/2000/svg}"
ET.register_namespace("", "http://www.w3.org/2000/svg")

RED = "#E11D48"


def annotate_file(src_path: str, devs: list[dict], out_path: str) -> int:
    tree = ET.parse(src_path)
    root = tree.getroot()
    for d in devs:
        x, y, w, h = d["box"]
        ov = ET.SubElement(root, "rect", {
            "x": str(max(0, x)), "y": str(max(0, y)),
            "width": str(max(8, w)), "height": str(max(8, h)),
            "fill": "none", "stroke": RED, "stroke-width": "2.5",
            "data-dev": str(d["seq"]),
        })
        ET.SubElement(root, "text", {
            "x": str(max(0, x)), "y": str(max(0, y - 4)),
            "font-family": "sans-serif", "font-size": "13",
            "fill": RED, "font-weight": "700",
        }).text = f"#{d['seq']} {d['problem_type']}"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tree.write(out_path, encoding="utf-8", xml_declaration=True)
    return len(devs)


def annotate_all(devs: list[dict], corpus_root: str, out_dir: str) -> dict:
    """返回 {文件 -> 标注副本路径}。"""
    os.makedirs(out_dir, exist_ok=True)
    by_file: dict[str, list[dict]] = {}
    for d in devs:
        by_file.setdefault(d["file"], []).append(d)
    out = {}
    for rel, ds in by_file.items():
        src = os.path.join(corpus_root, rel)
        dst = os.path.join(out_dir, os.path.basename(rel).replace(".svg", ".annotated.svg"))
        annotate_file(src, ds, dst)
        out[rel] = dst
    return out
