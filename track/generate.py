# -*- coding: utf-8 -*-
"""S3-TRK-001 埋点事件字典生成器。

从 track/event_dictionary.yaml 生成：
  docs/event_dictionary.md         Markdown 文档
  sdk/events.d.ts                  TypeScript 类型定义
  server/schema/<event>.json       服务端校验 JSON Schema（每事件一份）

加载时即校验：13 个事件、props 为合法 JSON Schema、黑名单字段名报错。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DICT_PATH = ROOT / "track" / "event_dictionary.yaml"
MD_PATH = ROOT / "docs" / "event_dictionary.md"
DTS_PATH = ROOT / "sdk" / "events.d.ts"
SCHEMA_DIR = ROOT / "server" / "schema"

EXPECTED_EVENTS = 13
PROP_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
EVENT_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class DictionaryError(SystemExit):
    pass


def _check_blacklist(props: dict, event_name: str, blacklist: list) -> None:
    for field in (props or {}).get("properties", {}) or {}:
        low = field.lower()
        for bad in blacklist:
            if low == bad.lower() or bad.lower() in low:
                raise DictionaryError(
                    f"[blacklist] 事件 {event_name} 字段 {field!r} 命中个人信息黑名单 "
                    f"({bad!r})，禁止定义")


def load_dictionary(path: Path = DICT_PATH) -> dict:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    blacklist = raw.get("blacklist") or []
    events = raw.get("events") or []
    if len(events) != EXPECTED_EVENTS:
        raise DictionaryError(
            f"[count] 事件数 {len(events)} != {EXPECTED_EVENTS}（首批核心事件必须齐全）")
    names = set()
    for ev in events:
        name = ev.get("name", "")
        if not EVENT_NAME_RE.match(name):
            raise DictionaryError(f"[name] 事件名非法: {name!r}")
        if name in names:
            raise DictionaryError(f"[duplicate] 事件名重复: {name}")
        names.add(name)
        if ev.get("status") not in ("active", "deprecated"):
            raise DictionaryError(f"[status] {name} status 非法: {ev.get('status')!r}")
        if ev.get("status") == "deprecated" and not ev.get("deprecated_reason"):
            raise DictionaryError(f"[deprecated] {name} 缺 deprecated_reason")
        if not re.match(r"^\d+\.\d+\.\d+$", str(ev.get("version", ""))):
            raise DictionaryError(f"[version] {name} 版本号非 semver: {ev.get('version')!r}")
        props = ev.get("props")
        if not isinstance(props, dict) or props.get("type") != "object":
            raise DictionaryError(f"[props] {name} props 必须是 type=object 的 JSON Schema")
        for field, spec in (props.get("properties") or {}).items():
            if not PROP_NAME_RE.match(field):
                raise DictionaryError(f"[field] {name}.{field} 字段名非法")
            if not isinstance(spec, dict) or "type" not in spec:
                raise DictionaryError(f"[schema] {name}.{field} 缺 type")
            if spec.get("enum") is not None and not spec["enum"]:
                raise DictionaryError(f"[enum] {name}.{field} enum 不能为空")
        _check_blacklist(props, name, blacklist)
    return raw


def _ts_type(spec: dict) -> str:
    t = spec.get("type")
    mapping = {"string": "string", "integer": "number", "number": "number",
               "boolean": "boolean"}
    if spec.get("enum"):
        return " | ".join(json.dumps(v, ensure_ascii=False) for v in spec["enum"])
    return mapping.get(t, "unknown")


def _interface(ev: dict) -> str:
    name = ev["name"]
    pascal = "".join(w.capitalize() for w in name.split("_"))
    lines = [f"export interface {pascal}Props {{"]
    props = ev["props"].get("properties") or {}
    required = set()
    for k, v in props.items():
        if isinstance(v, dict) and v.get("required"):
            required.add(k)
    for k, v in props.items():
        opt = "" if k in required else "?"
        desc = (v.get("description") or "").replace("*/", "")
        lines.append(f"  /** {desc} */")
        lines.append(f"  {k}{opt}: {_ts_type(v)};")
    lines.append("}")
    return "\n".join(lines)


def generate_md(raw: dict) -> str:
    out = ["# 埋点事件字典（首批 13 个核心事件）", "",
           "> 本文件由 track/generate.py 自动生成，请勿手工修改；",
           "> 变更请修改 track/event_dictionary.yaml 并走数据管理员评审流程。", ""]
    for ev in raw["events"]:
        out.append(f"## {ev['name']}")
        out.append("")
        out.append(f"- 说明：{ev['description']}")
        out.append(f"- 触发时机：{ev['trigger']}")
        out.append(f"- 所在页面：{ev['page']}")
        out.append(f"- 自动采集：{'是' if ev['auto_collect'] else '否'}")
        out.append(f"- 负责人：{ev['owner']}")
        out.append(f"- 版本：{ev['version']}　状态：{ev['status']}")
        out.append("")
        out.append("| 字段 | 类型 | 必填 | 说明 |")
        out.append("|---|---|---|---|")
        props = ev["props"].get("properties") or {}
        if not props:
            out.append("| （无属性） | | | |")
        for k, v in props.items():
            req = "是" if v.get("required") else "否"
            enum = f"；取值 {'/'.join(map(str, v['enum']))}" if v.get("enum") else ""
            out.append(f"| {k} | {v.get('type')} | {req} | {v.get('description','')}{enum} |")
        out.append("")
    return "\n".join(out)


def generate_dts(raw: dict) -> str:
    out = ["// 自动生成：track/generate.py —— 请勿手工修改",
           "// 会员空间平台埋点事件 SDK 类型定义（首批 13 个核心事件）", ""]
    for ev in raw["events"]:
        out.append(_interface(ev))
        out.append("")
    return "\n".join(out)


def generate_schemas(raw: dict) -> dict:
    out = {}
    for ev in raw["events"]:
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": ev["name"],
            "type": "object",
            "properties": ev["props"].get("properties") or {},
            "additionalProperties": False,
            "required": [k for k, v in (ev["props"].get("properties") or {}).items()
                         if isinstance(v, dict) and v.get("required")],
            "x_meta": {"version": ev["version"], "status": ev["status"],
                       "owner": ev["owner"]},
        }
        out[ev["name"]] = schema
    return out


def generate(root: Path = ROOT, out_md: Path = MD_PATH, out_dts: Path = DTS_PATH,
             out_dir: Path = SCHEMA_DIR) -> None:
    raw = load_dictionary(root / "track" / "event_dictionary.yaml")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_dts.parent.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_md.write_text(generate_md(raw), encoding="utf-8", newline="\n")
    out_dts.write_text(generate_dts(raw), encoding="utf-8", newline="\n")
    for name, schema in generate_schemas(raw).items():
        p = out_dir / f"{name}.json"
        p.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8", newline="\n")


if __name__ == "__main__":
    try:
        generate()
        print("generated: docs/event_dictionary.md, sdk/events.d.ts, server/schema/*.json")
    except DictionaryError as e:
        print(e)
        sys.exit(1)
