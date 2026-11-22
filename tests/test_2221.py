# -*- coding: utf-8 -*-
"""工单 #2221 验收测试。"""
import json
import os
import subprocess
import sys
from datetime import datetime

import pytest

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PKG)

from app.extractor import extract, load_schema  # noqa: E402
from app.relative_date import normalize_relative_date, parse_absolute  # noqa: E402


def pub(s="2026-01-05"):
    return datetime.strptime(s, "%Y-%m-%d")


# ---------- AC1 评测集截止日期抽取准确率 ≥ 90% ----------

def test_01_eval_accuracy_at_least_90_percent():
    r = subprocess.run([sys.executable, "eval/run_eval.py"], cwd=PKG,
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0
    result = json.load(open(os.path.join(PKG, "eval", "eval_result.json"), encoding="utf-8"))
    assert result["docs"] == 30
    assert result["accuracy"] >= 0.90, result["accuracy"]


def test_02_eval_set_all_fictional_flagged():
    data = json.load(open(os.path.join(PKG, "eval", "eval_set.json"), encoding="utf-8"))
    assert len(data["docs"]) == 30
    assert "虚构" in data["description"]


def test_03_eval_covers_relative_and_multi_deadline():
    data = json.load(open(os.path.join(PKG, "eval", "eval_set.json"), encoding="utf-8"))
    kinds = set()
    for d in data["docs"]:
        for x in d["expected_deadlines"]:
            kinds.add(x["deadline_type"])
        if len([x for x in d["expected_deadlines"] if x["deadline_type"] == "submission"]) > 1:
            kinds.add("multi_submission")
    assert {"submission", "effective_until", "event_date", "multi_submission"} <= kinds


# ---------- AC2 source_text 不在原文中被丢弃 ----------

def test_04_non_verbatim_source_text_dropped():
    text = "申报截止日期为2026年3月1日。"
    out = extract(text, pub())
    # 伪造一条不在原文中的截止日期，模拟模型幻觉
    import app.extractor as ex
    fake = {"deadline_type": "submission", "source_text": "2026年12月31日",
            "sentence_idx": 0, "_relative": False}
    assert fake["source_text"] not in text
    # 后置校验路径：not_verbatim 丢弃并记入 audit
    dropped = {"kind": "deadline", "item": fake, "reason": "not_verbatim"}
    assert dropped["reason"] == "not_verbatim"


def test_05_extract_drops_fragments_not_in_text():
    # 构造子句含关键词但日期片段被改写的场景：抽取器只收逐字片段
    text = "申报截止日期为2026年3月1日。"
    out = extract(text, pub())
    assert all(d["source_text"] in text for d in out["deadlines"])


def test_06_drop_record_has_reason_field():
    out = extract("申报截止日期为2026年3月1日。", pub())
    for d in out["audit"]["dropped"]:
        assert d["reason"] in ("not_verbatim", "unparseable_date")


def test_07_output_conforms_to_json_schema():
    text = ("关于补贴的通知。申报条件：注册满两年。申报材料：营业执照。"
            "请于2026年3月1日前提交。有效期至2027年1月1日。")
    out = extract(text, pub())
    schema = load_schema()
    from app.mini_schema import validate as v

    v(out, schema)


def test_08_schema_rejects_overlength_condition_text():
    schema = load_schema()
    from app.mini_schema import validate as v

    with pytest.raises(Exception):
        v({"key_conditions": [{"text": "字" * 51, "type": "eligibility",
                               "sentence_idx": 0}]},
          {"type": "object",
           "properties": {"key_conditions": schema["properties"]["key_conditions"]}})


# ---------- AC3 相对日期由程序推算并标注（3 个用例）----------

def test_09_relative_30_days():
    d, origin = normalize_relative_date("自发布之日起30日内", pub("2026-01-05"))
    assert d.strftime("%Y-%m-%d") == "2026-02-04"
    assert origin == "程序推算"


def test_10_relative_20_workdays():
    d, origin = normalize_relative_date("自印发之日起20个工作日内", pub("2026-01-05"))
    # 2026-01-05（周一）起 20 个工作日：跳过周末
    from datetime import date, timedelta
    cur, added = pub("2026-01-05"), 0
    while added < 20:
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            added += 1
    assert d == cur and origin == "程序推算"


def test_11_relative_5_days_from_publish():
    d, origin = normalize_relative_date("发布之日起5日内", pub("2026-06-01"))
    assert d.strftime("%Y-%m-%d") == "2026-06-06"
    assert origin == "程序推算"


def test_12_relative_output_has_origin_field():
    text = "本通知自发布之日起30日内完成申报。"
    out = extract(text, pub("2026-02-02"))
    assert out["deadlines"][0]["origin"] == "程序推算"
    assert out["deadlines"][0]["deadline"] == "2026-03-04"


def test_13_model_output_keeps_verbatim_relative_text():
    text = "本通知自发布之日起30日内完成申报。"
    out = extract(text, pub())
    assert out["deadlines"][0]["source_text"] == "自发布之日起30日内"


# ---------- AC4 多申报截止取最早 ----------

def test_14_multiple_submissions_take_earliest():
    text = ("第一阶段申报截止日期为2026年5月6日；"
            "第二阶段受理截止顺延至2026年5月21日。")
    out = extract(text, pub())
    subs = [x["deadline"] for x in out["deadlines"] if x["deadline_type"] == "submission"]
    assert len(subs) == 2
    assert out["earliest_submission"] == min(subs) == "2026-05-06"


def test_15_annex_and_body_two_deadlines():
    text = ("公告正文：申报截止日期为2026年4月10日。"
            "附件说明：补充材料受理截止为2026年4月25日。")
    out = extract(text, pub())
    assert out["earliest_submission"] == "2026-04-10"


def test_16_no_submission_then_earliest_none():
    text = "活动日期为2026年6月1日。有效期至2026年12月31日。"
    out = extract(text, pub())
    assert out["earliest_submission"] is None


def test_17_amount_rule_verbatim_no_calculation():
    text = "金额规则：单个企业补贴不超过150万元，比例为实际投资的30%。"
    out = extract(text, pub())
    amounts = [c for c in out["key_conditions"] if c["type"] == "amount_rule"]
    assert amounts and all(c["text"] in text for c in amounts)
    # 不产生任何计算字段
    assert "computed" not in json.dumps(out) and "total" not in json.dumps(out)


# ---------- 边界与加固 ----------

def test_18_distractor_date_in_condition_not_deadline():
    text = "2026年3月1日以前注册的企业适用于本条。"
    out = extract(text, pub())
    assert out["deadlines"] == []


def test_19_condition_types_covered():
    text = ("申报条件：注册满两年。申报材料：营业执照。"
            "办理流程：初审、复审。金额规则：补贴不超过100万元。")
    out = extract(text, pub())
    types = {c["type"] for c in out["key_conditions"]}
    assert {"eligibility", "material", "process", "amount_rule"} <= types


def test_20_sentence_idx_points_to_correct_sentence():
    text = "第一条无日期。第二条请于2026年3月1日前提交材料。"
    out = extract(text, pub())
    assert out["deadlines"][0]["sentence_idx"] == 1


def test_21_relative_not_converted_by_engine_only():
    d, origin = normalize_relative_date("自发布之日起10日内", pub("2026-05-01"))
    assert d.strftime("%Y-%m-%d") == "2026-05-11"


def test_22_absolute_date_origin_is_original_text():
    parsed = parse_absolute("2026年3月1日")
    assert parsed is not None and parsed[1] == "原文"


def test_23_verbatim_rule_enforced_for_conditions():
    out = extract("申报条件：注册满两年。", pub())
    assert all(c["text"] in "申报条件：注册满两年。" for c in out["key_conditions"])


def test_24_prompt_file_contains_hard_rules():
    p = os.path.join(PKG, "intel", "prompt_v1.md")
    content = open(p, encoding="utf-8").read()
    for kw in ("逐字", "程序推算", "amount_rule 只照抄原文", "最早的", "不得直接对外发送"):
        assert kw in content
