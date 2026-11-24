"""结构化输出校验器：按（schema_id, schema_version）注册的 JSON Schema 校验 ai_content。

不合格抛 SchemaValidationError，接口层转 422 且不落库。
"""
import jsonschema

# (schema_id, schema_version) -> JSON Schema
# schema 由模型网关统一登记；本单内置最小注册表，真实环境由 schema 管理服务提供。
SCHEMA_REGISTRY: dict[tuple[str, str], dict] = {
    ("member_space.chat_summary", "1.0"): {
        "type": "object",
        "required": ["summary", "keywords", "confidence_score"],
        "properties": {
            "summary": {"type": "string", "minLength": 1},
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
            "confidence_score": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "additionalProperties": False,
    },
    ("member_space.resource_match", "1.0"): {
        "type": "object",
        "required": ["match_reason", "confidence_score"],
        "properties": {
            "match_reason": {"type": "string", "minLength": 1},
            "candidate_ids": {"type": "array", "items": {"type": "string"}},
            "confidence_score": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "additionalProperties": False,
    },
}


class SchemaValidationError(ValueError):
    """ai_content 不符合登记 schema 时抛出。"""


def validate_ai_content(schema_id: str, schema_version: str, ai_content) -> None:
    schema = SCHEMA_REGISTRY.get((schema_id, schema_version))
    if schema is None:
        raise SchemaValidationError(
            f"unknown schema: {schema_id}@{schema_version}"
        )
    try:
        jsonschema.validate(instance=ai_content, schema=schema)
    except jsonschema.exceptions.ValidationError as exc:
        raise SchemaValidationError(
            f"ai_content failed schema {schema_id}@{schema_version}: {exc.message}"
        ) from exc
