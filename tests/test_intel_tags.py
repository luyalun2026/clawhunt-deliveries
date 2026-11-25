# -*- coding: utf-8 -*-
"""S5-INTEL-017 测试：维度计数、幂等导入、校验脚本、CRM 映射与 missing 清单。"""
import os, sqlite3, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = os.path.join(ROOT, "seed", "intel_tags.yaml")
PY = sys.executable

sys.path.insert(0, os.path.join(ROOT, "tools"))
from import_tags import load_seed


def _seed():
    return load_seed(SEED)


def test_ac1_dimension_counts():
    """AC1：policy_type 10、industry ≥12、qualification ≥6，共 5 维度。"""
    data = _seed()
    assert set(data) == {"policy_type", "industry", "region", "qualification", "company_size"}
    assert len(data["policy_type"]) == 10
    assert len(data["industry"]) >= 12
    assert len(data["qualification"]) >= 6


def test_ac2_idempotent_import(tmp_path):
    """AC2：导入命令重复执行两次后无重复记录。"""
    import import_tags
    db = str(tmp_path / "intel.db")

    def run_once():
        con = sqlite3.connect(db)
        con.execute(import_tags.DDL)
        data = _seed()
        for dim, tags in data.items():
            for t in tags:
                sql, params = import_tags.upsert_sql(dim, t)
                con.execute(sql, params)
        con.commit()
        total = con.execute("SELECT COUNT(*) FROM intel_tags").fetchone()[0]
        con.close()
        return total

    t1 = run_once()
    t2 = run_once()
    assert t1 == t2, f"第二次导入后计数变化: {t1} -> {t2}"


def test_ac3_validate_script(tmp_path):
    """AC3：校验脚本对种子全通过；对残缺种子退出码非 0。"""
    r = subprocess.run([PY, os.path.join(ROOT, "tools", "validate_tags.py"), "--seed", SEED],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "全通过" in r.stdout

    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "policy_type:\n"
        "  - code: x1\n"
        "    name: 测试\n"
        "    definition: " + "超" * 51 + "\n"
        "    positives: [\"只一条\"]\n",
        encoding="utf-8")
    r2 = subprocess.run([PY, os.path.join(ROOT, "tools", "validate_tags.py"), "--seed", str(bad)],
                        capture_output=True, text=True)
    assert r2.returncode != 0
    assert "51" in r2.stdout and "正例" in r2.stdout


def test_ac4_mapping_and_missing():
    """AC4：每个 industry 标签有 crm_tag_code 字段；缺失项单独列出。"""
    data = _seed()
    mapped, missing = [], []
    for t in data["industry"]:
        code = t.get("crm_tag_code", "__absent__")
        if code is None or code == "__absent__":
            missing.append(t["code"])
        else:
            mapped.append((t["code"], code))
    assert len(mapped) + len(missing) == len(data["industry"])
    assert mapped, "映射表为空"
    assert missing, "应存在待核心团队确认的缺失项（现代农业/文化旅游）"

    md = open(os.path.join(ROOT, "docs", "crm_mapping.md"), encoding="utf-8").read()
    for ind, crm in mapped:
        assert ind in md and crm in md, f"映射 {ind}->{crm} 未写入文档"
    assert "待确认" in md


def test_duplicate_code_rejected(tmp_path):
    """边界：重复 code 被导入拒绝。"""
    dup = tmp_path / "dup.yaml"
    dup.write_text(
        "company_size:\n"
        "  - {code: a, name: 甲, definition: 测试定义, positives: [x, y], negative: z}\n"
        "  - {code: a, name: 乙, definition: 测试定义, positives: [x, y], negative: z}\n",
        encoding="utf-8")
    import pytest
    with pytest.raises(ValueError):
        load_seed(str(dup))


def test_definition_over_50_rejected(tmp_path):
    """边界：定义 51 字被校验拦截。"""
    long_def = "长" * 51
    seed = tmp_path / "long.yaml"
    seed.write_text(f"region:\n  - {{code: r1, name: 甲, definition: {long_def}, positives: [x, y], negative: z}}\n",
                    encoding="utf-8")
    r = subprocess.run([PY, os.path.join(ROOT, "tools", "validate_tags.py"), "--seed", str(seed)],
                       capture_output=True, text=True)
    assert r.returncode != 0 and "50" in r.stdout
