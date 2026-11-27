# -*- coding: utf-8 -*-
"""S3-TRK-001 测试：AC1/AC2/AC3 + 边界。"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from track.generate import (DICT_PATH, DictionaryError, generate, generate_dts,
                            generate_md, generate_schemas, load_dictionary)

# ---------------- AC1 ----------------
def test_ac1_dictionary_13_events_with_props_schema():
    raw = load_dictionary(DICT_PATH)
    assert len(raw["events"]) == 13
    expected = {"app_launch", "page_view", "auth_success", "auth_apply",
                "resource_view", "resource_publish", "connect_request",
                "event_view", "event_register", "event_checkin", "faq_ask",
                "faq_feedback", "share"}
    assert {e["name"] for e in raw["events"]} == expected
    for ev in raw["events"]:
        assert ev["props"]["type"] == "object"
        assert isinstance(ev["props"].get("properties"), dict)

def test_ac1_given_props_fields_present():
    raw = load_dictionary(DICT_PATH)
    by_name = {e["name"]: e for e in raw["events"]}
    assert set(by_name["resource_view"]["props"]["properties"]) == {"item_id", "from"}
    assert set(by_name["resource_publish"]["props"]["properties"]) == {"item_id", "kind"}
    assert set(by_name["event_register"]["props"]["properties"]) == {"event_id", "signup_state"}
    assert set(by_name["share"]["props"]["properties"]) == {"page", "target_type", "target_id"}
    assert "keyword" in by_name["faq_ask"]["props"]["properties"]

# ---------------- AC2 ----------------
def test_ac2_regenerated_files_byte_identical():
    tmp = Path(tempfile.mkdtemp())
    try:
        generate(ROOT, tmp / "doc.md", tmp / "events.d.ts", tmp / "schema")
        assert (tmp / "doc.md").read_bytes() == (ROOT / "docs" / "event_dictionary.md").read_bytes()
        assert (tmp / "events.d.ts").read_bytes() == (ROOT / "sdk" / "events.d.ts").read_bytes()
        for p in (ROOT / "server" / "schema").glob("*.json"):
            assert (tmp / "schema" / p.name).read_bytes() == p.read_bytes()
        assert len(list((tmp / "schema").glob("*.json"))) == 13
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_ac2_ts_interface_required_not_optional():
    dts = (ROOT / "sdk" / "events.d.ts").read_text(encoding="utf-8")
    assert "export interface EventRegisterProps {" in dts
    seg = dts.split("export interface EventRegisterProps {")[1].split("}")[0]
    assert "  event_id: string;" in seg        # required → 无 ?
    assert "  signup_state:" in seg and '"signed" | "waitlisted"' in dts

# ---------------- AC3 ----------------
def _write_bad(tmp: Path, field: str = "phone") -> Path:
    raw = yaml.safe_load(DICT_PATH.read_text(encoding="utf-8"))
    raw["events"][1]["props"]["properties"][field] = {"type": "string", "required": True}
    p = tmp / "bad.yaml"
    p.write_text(yaml.dump(raw, allow_unicode=True), encoding="utf-8")
    return p

def test_ac3_blacklist_field_raises(tmp_path):
    p = _write_bad(tmp_path, "phone")
    with pytest.raises(DictionaryError) as e:
        load_dictionary(p)
    assert "phone" in str(e.value)

def test_ac3_blacklist_chinese_variant_raises(tmp_path):
    p = _write_bad(tmp_path, "手机号")
    with pytest.raises(DictionaryError) as e:
        load_dictionary(p)
    assert "手机号" in str(e.value)

# ---------------- 边界 ----------------
def test_duplicate_event_name_raises(tmp_path):
    raw = yaml.safe_load(DICT_PATH.read_text(encoding="utf-8"))
    dup = dict(raw["events"][0])
    dup["name"] = raw["events"][1]["name"]  # 与既有事件重名，总数仍为 13
    raw["events"][0] = dup
    p = tmp_path / "dup.yaml"
    p.write_text(yaml.dump(raw, allow_unicode=True), encoding="utf-8")
    with pytest.raises(DictionaryError) as e:
        load_dictionary(p)
    assert "duplicate" in str(e.value).lower()

def test_invalid_status_raises(tmp_path):
    raw = yaml.safe_load(DICT_PATH.read_text(encoding="utf-8"))
    raw["events"][0]["status"] = "draft"
    p = tmp_path / "st.yaml"
    p.write_text(yaml.dump(raw, allow_unicode=True), encoding="utf-8")
    with pytest.raises(DictionaryError):
        load_dictionary(p)

def test_non_object_props_raises(tmp_path):
    raw = yaml.safe_load(DICT_PATH.read_text(encoding="utf-8"))
    raw["events"][0]["props"] = {"type": "array"}
    p = tmp_path / "np.yaml"
    p.write_text(yaml.dump(raw, allow_unicode=True), encoding="utf-8")
    with pytest.raises(DictionaryError):
        load_dictionary(p)

def test_generated_server_schema_valid_json():
    p = ROOT / "server" / "schema" / "event_register.json"
    schema = json.loads(p.read_text(encoding="utf-8"))
    assert schema["required"] == ["event_id", "signup_state"]
    assert schema["additionalProperties"] is False
