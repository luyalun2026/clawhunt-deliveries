# -*- coding: utf-8 -*-
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.pipeline import load_cases, run


@pytest.fixture(scope="session")
def cases():
    return load_cases()


@pytest.fixture(scope="session")
def baseline(cases):
    return run(cases)


@pytest.fixture(scope="session")
def mini_cases():
    """每个模式 8 条 + 4 条噪声的小夹具，用于跑得快、又能验证同一套逻辑。"""
    rows = []
    for p, key in enumerate(["得分 0.34 低于阈值", "参数类型 期望整数", "未触发拒答 越权",
                             "引用悬空 c-1042"]):
        for i in range(8):
            rows.append({"case_key": "M%d-%02d" % (p + 1, i + 1), "pattern": "P%d" % (p + 1),
                         "tool": "t%d" % p, "tags": ["x"], "missed_points": ["p"],
                         "violation_types": ["v"], "severity": "medium",
                         "output_excerpt": "%s 第 %d 条" % (key, i + 1)})
    for i in range(4):
        rows.append({"case_key": "N-%02d" % (i + 1), "pattern": None, "tool": "pipeline",
                     "tags": ["env"], "missed_points": [], "violation_types": ["env_noise"],
                     "severity": "low", "output_excerpt": "环境噪声样本 %d：镜像拉取 502，重试恢复" % (i + 1)})
    return rows


@pytest.fixture(scope="session")
def mini_baseline(mini_cases):
    return run(mini_cases)


@pytest.fixture(scope="session")
def baseline_centers(mini_baseline):
    return [c["centroid"] for c in mini_baseline["clusters"]]
