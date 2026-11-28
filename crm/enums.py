from enum import StrEnum


class SqlEnum(StrEnum):
    @classmethod
    def sql_list(cls) -> str:
        return "(" + ", ".join(f"'{m.value}'" for m in cls) + ")"


class OpportunityStage(SqlEnum):
    DISCOVERY = "discovery"
    SITE_VISIT = "site_visit"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    WON = "won"
    LOST = "lost"


class SpaceType(SqlEnum):
    HOT_DESK = "hot_desk"
    FIXED_DESK = "fixed_desk"
    PRIVATE_OFFICE = "private_office"
    SUITE = "suite"


class MembershipTier(SqlEnum):
    FLEX = "flex"
    STANDARD = "standard"
    PREMIUM = "premium"
    STRATEGIC = "strategic"


class LostReason(SqlEnum):
    PRICE = "price"
    LOCATION = "location"
    SPACE = "space"
    COMPETITOR = "competitor"
    TIMING = "timing"
    OTHER = "other"
