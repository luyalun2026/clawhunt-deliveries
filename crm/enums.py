from enum import StrEnum


class SqlEnum(StrEnum):
    @classmethod
    def sql_list(cls) -> str:
        return "(" + ", ".join(f"'{m.value}'" for m in cls) + ")"


class MemberIdentity(SqlEnum):
    NONE = "none"
    PRIMARY = "primary"
    STAFF = "staff"


class WechatBindStatus(SqlEnum):
    UNBOUND = "unbound"
    BOUND = "bound"
    REVOKED = "revoked"
