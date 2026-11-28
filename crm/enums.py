from enum import StrEnum


class SqlEnum(StrEnum):
    @classmethod
    def sql_list(cls) -> str:
        return "(" + ", ".join(f"'{m.value}'" for m in cls) + ")"


class InteractionType(SqlEnum):
    VISIT = "visit"
    CALL = "call"
    WECHAT = "wechat"
    MEETING = "meeting"
    EVENT = "event"
    EMAIL = "email"
    OTHER = "other"


class InteractionSource(SqlEnum):
    MANUAL = "manual"
    IMPORT = "import"
    SYSTEM = "system"
