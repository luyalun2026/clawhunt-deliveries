import sqlalchemy as sa

from .base import Base, CommonMixin
from ..enums import MemberIdentity, WechatBindStatus


class CrmContact(CommonMixin, Base):
    """联系人表 crm_contact（工单 #2763）。

    约束要点：
    - 部分唯一索引三处（均限定未删除记录）：
      (org_id, wechat_unionid)、(org_id, mobile)、同一企业至多一名 primary；
    - CHECK：bound 必有 unionid；member_identity 非 none 必有 company_id；
    - 枚举值统一来自 crm/enums.py。
    """

    __tablename__ = "crm_contact"

    company_id = sa.Column(sa.Uuid, sa.ForeignKey("crm_company.id", name="fk_contact_company_id"), nullable=True)
    name = sa.Column(sa.String(50), nullable=False)
    title = sa.Column(sa.String(50))
    mobile = sa.Column(sa.String(16))
    email = sa.Column(sa.String(120))
    member_identity = sa.Column(sa.String(20), nullable=False, default=MemberIdentity.NONE.value)
    wechat_unionid = sa.Column(sa.String(64))
    wechat_openid = sa.Column(sa.String(64))
    wechat_bind_status = sa.Column(sa.String(20), nullable=False, default=WechatBindStatus.UNBOUND.value)
    wechat_bound_at = sa.Column(sa.DateTime(timezone=True))
    merged_into_id = sa.Column(sa.Uuid, sa.ForeignKey("crm_contact.id", name="fk_contact_merged_into_id", use_alter=True))

    __table_args__ = (
        sa.CheckConstraint(
            "wechat_bind_status <> 'bound' OR wechat_unionid IS NOT NULL",
            name="ck_contact_bound_unionid",
        ),
        sa.CheckConstraint(
            "member_identity = 'none' OR company_id IS NOT NULL",
            name="ck_contact_identity_company",
        ),
        sa.CheckConstraint(
            f"member_identity IN {MemberIdentity.sql_list()}",
            name="ck_contact_identity_enum",
        ),
        sa.CheckConstraint(
            f"wechat_bind_status IN {WechatBindStatus.sql_list()}",
            name="ck_contact_bind_enum",
        ),
        sa.Index(
            "uq_contact_org_unionid", "org_id", "wechat_unionid", unique=True,
            sqlite_where=sa.text("deleted_at IS NULL AND wechat_unionid IS NOT NULL"),
            postgresql_where=sa.text("deleted_at IS NULL AND wechat_unionid IS NOT NULL"),
        ),
        sa.Index(
            "uq_contact_org_mobile", "org_id", "mobile", unique=True,
            sqlite_where=sa.text("deleted_at IS NULL AND mobile IS NOT NULL"),
            postgresql_where=sa.text("deleted_at IS NULL AND mobile IS NOT NULL"),
        ),
        sa.Index(
            "uq_contact_company_primary", "company_id", unique=True,
            sqlite_where=sa.text("member_identity = 'primary' AND deleted_at IS NULL"),
            postgresql_where=sa.text("member_identity = 'primary' AND deleted_at IS NULL"),
        ),
        sa.Index("ix_contact_org_company", "org_id", "company_id"),
        sa.Index("ix_contact_org_identity", "org_id", "member_identity"),
    )


def normalize_mobile(raw: str) -> str:
    """手机号 E.164 规范化：+86 前缀 / 空格与连字符清洗。"""
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    if raw and raw.strip().startswith("+"):
        return "+" + digits
    if len(digits) == 11:
        return "+86" + digits
    return "+" + digits if raw and raw.strip().startswith("+") else digits
