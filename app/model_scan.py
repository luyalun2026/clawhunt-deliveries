# -*- coding: utf-8 -*-
"""响应模型自动发现：从 FastAPI 路由（而非手工清单）收集会员端 GET 接口的响应模型。

覆盖三种形态：
1. `response_model=Model`；
2. `response_model=list[Model]` / `Optional[Model]` 等泛型包装；
3. 模型字段本身是嵌套 BaseModel 或 `list[BaseModel]`（递归下钻）。

新增接口只要挂在 `/api/mini/` 下并声明 response_model，就会被扫描到，无需登记。
"""
from __future__ import annotations

import typing as t

from pydantic import BaseModel


def _unwrap(annotation):
    """剥掉 list/Optional/Union 等包装，取出内部的 BaseModel 类型（可能多个）。"""
    out = []
    origin = t.get_origin(annotation)
    if origin is None:
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            out.append(annotation)
        return out
    for arg in t.get_args(annotation):
        out.extend(_unwrap(arg))
    return out


def discover_response_models(app, prefix: str = "/api/mini/") -> dict[str, type[BaseModel]]:
    """返回 {模型名: 模型类}，含嵌套模型。"""
    found: dict[str, type[BaseModel]] = {}

    def add(model: type[BaseModel]) -> None:
        if model.__name__ in found:
            return
        found[model.__name__] = model
        for field in model.model_fields.values():
            for nested in _unwrap(field.annotation):
                add(nested)

    for route in getattr(app, "routes", []):
        path = getattr(route, "path", "")
        if not path.startswith(prefix):
            continue
        methods = getattr(route, "methods", set()) or set()
        if "GET" not in methods:
            continue
        model = getattr(route, "response_model", None)
        if model is None:
            continue
        for m in _unwrap(model):
            add(m)
    return found


def banned_hits(models: dict[str, type[BaseModel]], banned_keys) -> list[str]:
    hits: list[str] = []
    for model in models.values():
        for fname in model.model_fields:
            if fname in banned_keys:
                hits.append(f"{model.__name__}.{fname}")
    return sorted(hits)
