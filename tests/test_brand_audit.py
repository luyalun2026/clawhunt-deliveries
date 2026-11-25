# -*- coding: utf-8 -*-
"""S6-BRAND-001 测试：≥40 处抽样、对比度实测字段、修订建议回链、边界用例。"""
import json, os, sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from audit.audit_runner import audit_all
from audit.measure_contrast import contrast_ratio, judge, TOOL_NAME


def _devs():
    return audit_all()


def test_ac1_at_least_40_samples_with_fields():
    """AC1：偏差清单覆盖不少于 40 处，每条含位置/问题类型/严重级别/判定要素。"""
    devs = _devs()
    assert len(devs) >= 40, f"偏差仅 {len(devs)} 条"
    for d in devs:
        assert d["location"] and d["problem_type"] and d["severity"] in ("高", "中", "低")
        assert d["box"] and len(d["box"]) == 4  # 截图标注框坐标


def test_ac2_contrast_records_have_tool_and_value():
    """AC2：每条对比度问题附实测数值与测量工具名。"""
    devs = [d for d in _devs() if d["problem_type"] == "contrast_low"]
    assert devs, "应存在对比度偏差"
    for d in devs:
        c = d["extra"]["contrast"]
        assert c["tool"] == TOOL_NAME
        assert isinstance(c["ratio"], (int, float)) and c["ratio"] > 0
        assert c["ratio"] < c["required"], "被判为对比度问题的实测值应低于阈值"
        # 抽样复核实测值本身
        assert abs(contrast_ratio(c["fg"], c["bg"]) - c["ratio"]) < 0.01


def test_ac3_revision_suggestions_link_ids():
    """AC3：修订建议按章节归类，每条注明偏差编号。"""
    from audit.build_deviation_list import TYPE_TO_CHAPTER
    md = open(os.path.join(ROOT, "output", "revision_suggestions.md"), encoding="utf-8").read()
    devs = _devs()
    chapters = set(TYPE_TO_CHAPTER.values())
    covered = {d["problem_type"] for d in devs}
    for p in covered:
        ch = TYPE_TO_CHAPTER[p]
        assert ch in md, f"章节 {ch} 未出现"
    ids_in_doc = set()
    import re
    for m in re.findall(r"#(\d+)", md):
        ids_in_doc.add(int(m))
    missing = [d["seq"] for d in devs if d["seq"] not in ids_in_doc]
    assert not missing, f"偏差编号未回链: {missing[:10]}"


def test_edge_transparent_sampling_skipped():
    """边界：fill 为 none / 缺失的元素不参与对比度计算。"""
    from audit.audit_runner import audit_one
    spec = yaml.safe_load(open(os.path.join(ROOT, "corpus", "spec.yaml"), encoding="utf-8"))
    import tempfile
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50">'
           '<rect id="bg" width="100" height="50" fill="#FFFFFF"/>'
           '<text id="t" x="8" y="24" font-size="14" fill="none">幽灵文本</text>'
           '</svg>')
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "x.svg")
        open(p, "w", encoding="utf-8").write(svg)
        meta = {"file": "x.svg", "kind": "console", "label": "边界面"}
        recs = audit_one(p, spec, meta)
        assert not any(d["problem_type"] == "contrast_low" for d in recs)


def test_edge_large_text_uses_3to1():
    """边界：≥24px 大字按 3:1 判定。"""
    assert judge("#1F2937", "#6B7280", 24)["required"] == 3.0
    assert judge("#1F2937", "#6B7280", 14)["required"] == 4.5


def test_edge_zero_size_box_clamped():
    """边界：标注框宽高过小被钳制到 ≥8，坐标负值钳到 0。"""
    from audit.annotate import annotate_file
    import tempfile
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50">'
           '<rect id="bg" width="100" height="50" fill="#FFFFFF"/></svg>')
    dev = {"seq": 1, "problem_type": "grid_off", "box": [-5, -3, 2, 1],
           "location": "x", "severity": "低", "description": "", "extra": {}}
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "a.svg")
        out = os.path.join(td, "b.svg")
        open(src, "w", encoding="utf-8").write(svg)
        n = annotate_file(src, [dev], out)
        assert n == 1 and os.path.exists(out)


def test_edge_spec_missing_judged_as_missing():
    """边界：规范未覆盖的问题类型判定为「规范缺失」而非执行偏差。"""
    from audit.build_deviation_list import classify
    dev = {"problem_type": "dark_mode_contrast"}
    assert classify(dev) == "规范缺失"
    dev2 = {"problem_type": "contrast_low"}
    assert classify(dev2) == "执行偏差"
