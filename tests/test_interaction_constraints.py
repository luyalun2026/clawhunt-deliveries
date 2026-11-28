"""#2770 约束测试（AC 逐条 + 边界加固）。全部虚构数据。"""
import os
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crm.models.interaction import CrmInteraction

ORG1 = uuid.uuid4()
C1 = uuid.uuid4()
NOW = datetime.now(timezone.utc)


def _base(**kw):
    p = dict(org_id=ORG1, company_id=C1, type="visit", occurred_at=NOW, summary="例行拜访，客户对流动工位感兴趣。")
    p.update(kw)
    return CrmInteraction(**p)


def test_ac1_columns_and_roundtrip(migrated_engine):
    insp = inspect(migrated_engine)
    cols = {c["name"] for c in insp.get_columns("crm_interaction")}
    assert {"id", "org_id", "company_id", "contact_id", "type", "occurred_at", "duration_minutes",
            "summary", "next_action", "next_action_due", "lead_id", "opportunity_id",
            "source", "owner_user_id", "merged_into_id"} <= cols
    # 三个 DESC 复合索引真实存在（反射断言）
    idx = {i["name"] for i in insp.get_indexes("crm_interaction")}
    assert {"ix_int_org_company_occ", "ix_int_org_contact_occ", "ix_int_org_owner_occ",
            "ix_int_summary_trgm"} <= idx
    # lead_id / opportunity_id 只建列不建外键（由线索表、商机表迁移补建）
    if migrated_engine.dialect.name == "postgresql":
        fks = {f["constrained_columns"][0] for f in insp.get_foreign_keys("crm_interaction")}
        assert "lead_id" not in fks and "opportunity_id" not in fks


class TestAC2DurationAndSummaryChecks:
    def test_duration_1441_rejected_1440_ok(self, migrated_engine):
        with Session(migrated_engine) as s:
            s.add(_base(duration_minutes=1441))
            with pytest.raises(IntegrityError):
                s.commit()
            s.rollback()
            s.add(_base(duration_minutes=1440))
            s.commit()

    def test_summary_empty_and_5001_rejected_5000_ok(self, migrated_engine):
        with Session(migrated_engine) as s:
            s.add(_base(summary=""))
            with pytest.raises(IntegrityError):
                s.commit()
            s.rollback()
            s.add(_base(summary="长" * 5001))
            with pytest.raises(IntegrityError):
                s.commit()
            s.rollback()
            s.add(_base(summary="记"))
            s.add(_base(summary="尾" * 5000))
            s.commit()


class TestAC3ExplainUsesCompositeIndex:
    @pytest.mark.skipif(not os.environ.get("PG_DSN"), reason="未配置 PG_DSN（无本地 PG16）；pg_ddl.sql + seed_10k.py + explain_query.py 提供一键复现")
    def test_explain_hits_org_company_occurred_index(self, migrated_engine):
        import subprocess
        import sys
        import pathlib
        ROOT = pathlib.Path(__file__).resolve().parents[1]
        subprocess.run([sys.executable, "seed_10k.py"], cwd=ROOT, check=True)
        out = subprocess.run([sys.executable, "explain_query.py"], cwd=ROOT, check=True,
                             capture_output=True, text=True, encoding="utf-8")
        assert "ix_int_org_company_occ" in out.stdout


class TestEdgeCases:
    def test_type_enum_rejected(self, migrated_engine):
        with Session(migrated_engine) as s:
            s.add(_base(type="fax"))
            with pytest.raises(IntegrityError):
                s.commit()
            s.rollback()

    def test_occurred_at_required(self, migrated_engine):
        with Session(migrated_engine) as s:
            s.add(_base(occurred_at=None))
            with pytest.raises(IntegrityError):
                s.commit()
            s.rollback()

    def test_source_default_manual_and_enum(self, migrated_engine):
        with Session(migrated_engine) as s:
            a = _base()
            s.add(a)
            s.commit()
            assert a.source == "manual"
            s.add(_base(source="fax"))
            with pytest.raises(IntegrityError):
                s.commit()
            s.rollback()

    def test_next_action_fields(self, migrated_engine):
        with Session(migrated_engine) as s:
            s.add(_base(next_action="发送报价方案", next_action_due=NOW.date()))
            s.commit()

    def test_merged_into_self_reference(self, migrated_engine):
        with Session(migrated_engine) as s:
            a = _base(summary="首次接触")
            s.add(a)
            s.commit()
            b = _base(summary="合并入口", merged_into_id=a.id)
            s.add(b)
            s.commit()
            assert b.merged_into_id == a.id
