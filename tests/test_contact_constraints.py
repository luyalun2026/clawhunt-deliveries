"""#2763 约束测试（AC 逐条 + 边界加固）。全部虚构数据。"""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crm.models.company import CrmCompany
from crm.models.contact import CrmContact, normalize_mobile

ORG1 = uuid.uuid4()
ORG2 = uuid.uuid4()
C1 = uuid.uuid4()
NOW = datetime.now(timezone.utc)


def _base(**kw):
    p = dict(org_id=ORG1, name="张三", member_identity="none", wechat_bind_status="unbound")
    p.update(kw)
    return CrmContact(**p)


def test_ac1_roundtrip_and_zero_drift(migrated_engine):
    insp = inspect(migrated_engine)
    cols = {c["name"] for c in insp.get_columns("crm_contact")}
    assert {"id", "org_id", "site_id", "created_at", "created_by", "updated_at", "deleted_at",
            "company_id", "name", "title", "mobile", "email", "member_identity",
            "wechat_unionid", "wechat_openid", "wechat_bind_status", "wechat_bound_at",
            "merged_into_id"} <= cols


class TestAC2PrimaryUnique:
    def test_second_primary_rejected_then_staff_ok(self, migrated_engine):
        with Session(migrated_engine) as s:
            p1 = _base(company_id=C1, name="王甲", member_identity="primary")
            s.add(p1)
            s.commit()
            s.add(_base(company_id=C1, name="王乙", member_identity="primary"))
            with pytest.raises(IntegrityError):
                s.commit()
            s.rollback()
            p1.member_identity = "staff"
            s.commit()
            p2 = _base(company_id=C1, name="王乙", member_identity="primary")
            s.add(p2)
            s.commit()
            assert p2.id is not None


class TestAC3BoundUnionidCheck:
    def test_bound_without_unionid_rejected(self, migrated_engine):
        with Session(migrated_engine) as s:
            s.add(_base(name="李四", wechat_bind_status="bound", wechat_unionid=None))
            with pytest.raises(IntegrityError):
                s.commit()
            s.rollback()
            s.add(_base(name="李四", wechat_bind_status="bound", wechat_unionid=str(uuid.uuid4())))
            s.commit()


class TestAC4OrgUnionidPartialUnique:
    def test_same_org_rejected_cross_org_ok(self, migrated_engine):
        with Session(migrated_engine) as s:
            s.add(_base(org_id=ORG1, wechat_unionid="U1", name="赵六"))
            s.commit()
            s.add(_base(org_id=ORG1, wechat_unionid="U1", name="赵七"))
            with pytest.raises(IntegrityError):
                s.commit()
            s.rollback()
            s.add(_base(org_id=ORG2, wechat_unionid="U1", name="赵八"))
            s.commit()

    def test_soft_deleted_unionid_reusable(self, migrated_engine):
        with Session(migrated_engine) as s:
            a = _base(org_id=ORG1, wechat_unionid="U2", name="钱一")
            s.add(a)
            s.commit()
            a.deleted_at = NOW
            s.commit()
            s.add(_base(org_id=ORG1, wechat_unionid="U2", name="钱二"))
            s.commit()


class TestEdgeCases:
    def test_identity_none_requires_no_company_but_non_none_requires_company(self, migrated_engine):
        with Session(migrated_engine) as s:
            s.add(_base(name="孙一", member_identity="staff", company_id=None))
            with pytest.raises(IntegrityError):
                s.commit()
            s.rollback()
            s.add(_base(name="孙一", member_identity="none", company_id=None))
            s.commit()

    def test_org_mobile_partial_unique(self, migrated_engine):
        with Session(migrated_engine) as s:
            s.add(_base(org_id=ORG1, mobile="+8613800000001", name="周一"))
            s.commit()
            s.add(_base(org_id=ORG1, mobile="+8613800000001", name="周二"))
            with pytest.raises(IntegrityError):
                s.commit()
            s.rollback()
            s.add(_base(org_id=ORG2, mobile="+8613800000001", name="周三"))
            s.commit()

    def test_revoked_needs_no_unionid(self, migrated_engine):
        with Session(migrated_engine) as s:
            s.add(_base(name="吴一", wechat_bind_status="revoked", wechat_unionid=None))
            s.commit()

    def test_normalize_mobile_e164(self):
        assert normalize_mobile("13800000001") == "+8613800000001"
        assert normalize_mobile("+8613800000001") == "+8613800000001"
        assert normalize_mobile("138-0000-0001") == "+8613800000001"

    def test_merged_into_self_reference(self, migrated_engine):
        with Session(migrated_engine) as s:
            a = _base(name="郑一")
            s.add(a)
            s.commit()
            b = _base(name="郑二", merged_into_id=a.id)
            s.add(b)
            s.commit()
            assert b.merged_into_id == a.id
