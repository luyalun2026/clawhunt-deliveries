# -*- coding: utf-8 -*-
"""AC3：与上月按簇中心余弦对齐，正确标出 新出现 / 持续 / 已消失。"""
import json
import os

from app.pipeline import run
from app.rank import ALIGN_THRESHOLD


def _prev_file(tmp_path, centers):
    p = tmp_path / "prev_centers.json"
    p.write_text(json.dumps({"centers": centers}, ensure_ascii=False), encoding="utf-8")
    return str(p)


def test_13_ongoing_when_center_matches(mini_cases, tmp_path, baseline_centers):
    keep = baseline_centers[0]
    path = _prev_file(tmp_path, [{"name": "上月-阈值边界", "vector": keep}])
    out = run(mini_cases, prev_path=path, compute_ari=True)
    st = {c["name"]: c["alignment"]["status"] for c in out["clusters"]}
    assert "ongoing" in st.values()
    ongoing = [c for c in out["clusters"] if c["alignment"]["status"] == "ongoing"]
    assert ongoing and ongoing[0]["alignment"]["similarity"] >= ALIGN_THRESHOLD


def test_14_new_when_no_match(mini_cases, tmp_path):
    path = _prev_file(tmp_path, [{"name": "上月-完全无关", "vector": [0.0] * 512}])
    out = run(mini_cases, prev_path=path)
    assert all(c["alignment"]["status"] == "new" for c in out["clusters"])
    assert out["alignment_summary"]["new"]


def test_15_vanished_detected(mini_cases, tmp_path, baseline_centers):
    path = _prev_file(tmp_path, [
        {"name": "上月-会保留", "vector": baseline_centers[0]},
        {"name": "上月-已消失", "vector": [0.0] * 512},
    ])
    out = run(mini_cases, prev_path=path)
    assert "上月-已消失" in out["alignment_summary"]["vanished"]
    assert "上月-会保留" not in out["alignment_summary"]["vanished"]


def test_16_missing_prev_file_all_new(mini_cases, tmp_path):
    out = run(mini_cases, prev_path=str(tmp_path / "nope.json"))
    assert all(c["alignment"]["status"] == "new" for c in out["clusters"])
    assert out["alignment_summary"]["vanished"] == []


def test_17_alignment_does_not_change_ranking(mini_cases, tmp_path, baseline_centers):
    a = run(mini_cases)
    b = run(mini_cases, prev_path=_prev_file(tmp_path, [{"name": "上月", "vector": baseline_centers[0]}]))
    assert [x["cluster_id"] for x in a["top5"]] == [x["cluster_id"] for x in b["top5"]]
