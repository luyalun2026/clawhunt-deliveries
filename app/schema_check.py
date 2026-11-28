"""轻量 JSON Schema 校验（零第三方依赖）。

按 app/schema.json（draft 2020-12 常用子集）校验模型输出，支持关键字：
type / required / properties / additionalProperties / items /
minLength / maxLength / minimum / maximum。

extractor 在 _parse_model_json 解析成功之后调用 validate()；
返回错误列表（空列表 = 合规）。不合规与 JSON 解析失败同一口径：
重试（1 + JSON_RETRY_TIMES 次），仍失败按失败块处理（整组 llm_failed）。
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.json")
_cache: Dict[str, Dict] = {}


def load_schema(path: str = _SCHEMA_PATH) -> Dict:
    """加载并缓存 schema 文件。"""
    if path not in _cache:
        with open(path, encoding="utf-8") as f:
            _cache[path] = json.load(f)
    return _cache[path]


def _type_ok(val: Any, typ) -> bool:
    types = typ if isinstance(typ, list) else [typ]
    checks = {
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "string": lambda v: isinstance(v, str),
        "boolean": lambda v: isinstance(v, bool),
        "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
        "null": lambda v: v is None,
    }
    return any(checks[t](val) for t in types if t in checks)


def validate(obj: Any, schema: Optional[Dict] = None, path: str = "$") -> List[str]:
    """返回违规列表；空列表表示合规。"""
    schema = schema or load_schema()
    errs: List[str] = []
    t = schema.get("type")
    if t and not _type_ok(obj, t):
        return [f"{path}: 类型应为 {t}"]
    if isinstance(obj, dict):
        for k in schema.get("required", []):
            if k not in obj:
                errs.append(f"{path}: 缺少必填键 {k}")
        props = schema.get("properties", {})
        addl = schema.get("additionalProperties", True)
        for k, v in obj.items():
            if k in props:
                errs += validate(v, props[k], f"{path}.{k}")
            elif addl is False:
                errs.append(f"{path}: 不允许的额外键 {k}")
            elif isinstance(addl, dict):
                errs += validate(v, addl, f"{path}.{k}")
    if isinstance(obj, list):
        items = schema.get("items")
        if isinstance(items, dict):
            for i, v in enumerate(obj):
                errs += validate(v, items, f"{path}[{i}]")
    if isinstance(obj, str):
        if "minLength" in schema and len(obj) < schema["minLength"]:
            errs.append(f"{path}: 长度 {len(obj)} < minLength {schema['minLength']}")
        if "maxLength" in schema and len(obj) > schema["maxLength"]:
            errs.append(f"{path}: 长度 {len(obj)} > maxLength {schema['maxLength']}")
    if isinstance(obj, (int, float)) and not isinstance(obj, bool):
        if "minimum" in schema and obj < schema["minimum"]:
            errs.append(f"{path}: {obj} < minimum {schema['minimum']}")
        if "maximum" in schema and obj > schema["maximum"]:
            errs.append(f"{path}: {obj} > maximum {schema['maximum']}")
    return errs


def is_valid(obj: Any, schema: Optional[Dict] = None) -> bool:
    return not validate(obj, schema)
