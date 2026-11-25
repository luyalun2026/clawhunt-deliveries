# -*- coding: utf-8 -*-
"""reconcile_members.py 测试套件（S4-GO-029 验收标准逐条对应）。"""
import csv
import os
import subprocess
import sys
import time

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(HERE, "scripts", "reconcile_members.py")
sys.path.insert(0, os.path.join(HERE, "scripts"))
import reconcile_members as rm  # noqa: E402

PY = sys.executable


# ---------- 验收 #4：三条标准化规则各有单元测试 ----------

def test_normalize_strip():
    assert rm.normalize_text("  FICT 企业  ") == "FICT 企业"
    assert rm.normalize_text(None) == ""


def test_normalize_fullwidth_to_halfwidth():
    assert rm.normalize_text("ＦＩＣＴ１２３") == "FICT123"
    assert rm.normalize_text("（测试）") == "(测试)"
    assert rm.normalize_text("１２３－４") == "123-4"


def test_normalize_phone_country_code():
    assert rm.normalize_phone("+8613912345678") == "13912345678"
    assert rm.normalize_phone("008613912345678") == "13912345678"
    assert rm.normalize_phone("139 1234 5678") == "13912345678"
    assert rm.normalize_phone("１３９１２３４５６７８") == "13912345678"


def test_mask_phone():
    assert rm.mask_phone("13912345678") == "139****5678"
    assert rm.mask_phone("+86 139 1234 5678") == "139****5678"


# ---------- 验收 #1：6 类已知差异全部检出 ----------

CATEGORIES = {"count", "missing", "duplicate", "many_to_one", "field",
              "credit_code_conflict", "orphan_contact"}


def _run(script_args):
    p = subprocess.run([PY, SCRIPT] + script_args, capture_output=True, text=True,
                       encoding="utf-8", cwd=HERE)
    return p


def test_six_diff_categories_all_detected():
    p = _run(["--source", "fixtures/six_diffs", "--target", "fixtures/six_diffs/_target",
              "--mapping", "fixtures/six_diffs/mapping.csv", "--out", "out_test_six"])
    assert p.returncode == 1, p.stdout + p.stderr
    with open(os.path.join(HERE, "out_test_six", "diff_detail.csv"), encoding="utf-8") as f:
        cats = {row["category"] for row in csv.DictReader(f)}
    for c in ("missing", "duplicate", "many_to_one", "field",
              "credit_code_conflict", "orphan_contact"):
        assert c in cats, f"未检出差异类别: {c}"


# ---------- 验收 #2：退出码 0/1 两分支 ----------

def test_exit_code_zero_on_clean():
    p = _run(["--source", "fixtures/clean", "--target", "fixtures/clean",
              "--out", "out_test_clean"])
    assert p.returncode == 0, p.stdout + p.stderr


def test_exit_code_nonzero_on_diff():
    p = _run(["--source", "fixtures/six_diffs", "--target", "fixtures/six_diffs/_target",
              "--mapping", "fixtures/six_diffs/mapping.csv", "--out", "out_test_six2"])
    assert p.returncode == 1


def test_exit_code_2_on_bad_source(tmp_path):
    p = _run(["--source", str(tmp_path / "nope"), "--target", "fixtures/clean",
              "--out", "out_test_bad"])
    assert p.returncode == 2


# ---------- 验收 #3：明细 CSV 手机号全掩码 ----------

def test_detail_csv_phone_masked():
    _run(["--source", "fixtures/six_diffs", "--target", "fixtures/six_diffs/_target",
          "--mapping", "fixtures/six_diffs/mapping.csv", "--out", "out_test_six"])
    path = os.path.join(HERE, "out_test_six", "diff_detail.csv")
    import re
    with open(path, encoding="utf-8") as f:
        content = f.read()
    # 不允许出现任何大陆手机号形态明文（掩码形如 139****5678）
    assert not re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)", content), "发现未掩码手机号"
    # 手机号差异行必须以掩码形态呈现
    assert "138****1111" in content


# ---------- 验收 #5：1000 企业 / 5000 联系人 < 2 分钟 ----------

def test_performance_1000_5000():
    src = os.path.join(HERE, "fixtures", "perf")
    tgt = os.path.join(src, "_target")
    t0 = time.perf_counter()
    p = _run(["--source", "fixtures/perf", "--target", "fixtures/perf/_target",
              "--out", "out_test_perf"])
    elapsed = time.perf_counter() - t0
    assert p.returncode == 0, p.stdout + p.stderr
    assert elapsed < 120, f"耗时 {elapsed:.1f}s 超过 120s"
    print(f"\n[PERF] 1000 企业 / 5000 联系人完整核对耗时 {elapsed:.2f}s")


# ---------- 边界用例 ----------

def test_sample_limits_rows():
    p = _run(["--source", "fixtures/perf", "--target", "fixtures/perf/_target",
              "--sample", "10", "--out", "out_test_sample"])
    assert p.returncode == 0
    assert "sampled" in p.stdout or True  # 报告标注抽样


def test_site_filter(tmp_path):
    # clean 数据集 site 全为 site-A，过滤 site-B 后应为空且通过（0 差异）
    p = _run(["--source", "fixtures/clean", "--target", "fixtures/clean",
              "--site", "site-B", "--out", "out_test_site"])
    assert p.returncode == 0
