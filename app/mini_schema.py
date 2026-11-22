# -*- coding: utf-8 -*-
"""离线 JSON Schema 校验（子集实现）：覆盖本包 schema_v1.json 用到的关键字。

支持：type / required / properties / items / enum / const / maxLength / minLength /
pattern / minimum。设计为进程内等价实现，生产可替换为 jsonschema 库（口径一致）。
"""
from __future__ import annotations

import re

TYPE_MAP = {
    "object": dict, "array": list, "string": str,
    "integer": int, "number": (int, float), "boolean": bool,
}


def validate(instance, schema, path="$"):
    """校验失败抛 ValueError；通过返回 None。"""
    if "const" in schema and instance != schema["const"]:
        raise ValueError("%s: const 不匹配（期望 %r，得到 %r）" % (path, schema["const"], instance))

    stype = schema.get("type")
    if stype is not None:
        types = stype if isinstance(stype, list) else [stype]
        pytypes = [t for name in types for t in
                   ([TYPE_MAP[name]] if name in TYPE_MAP else name.split("||"))]
        # 允许 "string|null" 形式
        norm = []
        for name in types:
            if name.endswith("|null") or "|null" in name:
                norm.append("null")
            if name in TYPE_MAP:
                norm.append(name)
        if not isinstance(instance, type(None)) and "null" in norm and instance is None:
            return
        if instance is not None:
            matched = False
            for name in norm:
                if name == "null":
                    matched = matched or instance is None
                elif name == "integer":
                    matched = matched or (isinstance(instance, int) and not isinstance(instance, bool))
                else:
                    matched = matched or isinstance(instance, TYPE_MAP.get(name, type(None)))
            if not matched:
                raise ValueError("%s: 类型不符（期望 %s，得到 %s）" % (path, types, type(instance).__name__))

    if isinstance(instance, dict):
        for req in schema.get("required", []):
            if req not in instance:
                raise ValueError("%s: 缺少必填字段 %r" % (path, req))
        props = schema.get("properties", {})
        for key, sub in props.items():
            if key in instance:
                validate(instance[key], sub, "%s.%s" % (path, key))

    if isinstance(instance, list):
        if "items" in schema:
            for i, item in enumerate(instance):
                validate(item, schema["items"], "%s[%d]" % (path, i))

    if isinstance(instance, str):
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            raise ValueError("%s: 超过 maxLength=%d" % (path, schema["maxLength"]))
        if "minLength" in schema and len(instance) < schema["minLength"]:
            raise ValueError("%s: 短于 minLength=%d" % (path, schema["minLength"]))
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            raise ValueError("%s: 不匹配 pattern=%r" % (path, schema["pattern"]))

    if "enum" in schema and instance not in schema["enum"]:
        raise ValueError("%s: 不在枚举 %r 内" % (path, schema["enum"]))

    if isinstance(instance, int) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            raise ValueError("%s: 小于 minimum=%s" % (path, schema["minimum"]))
