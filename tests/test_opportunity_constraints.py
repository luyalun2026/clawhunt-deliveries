"""#2771 约束测试（AC 逐条 + 边界加固）。全部虚构数据。"""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crm.models.company import CrmCompany
from crm.models.opportunity import CrmOpportunity

ORG1 = uuid.uuid4()
C1 = uuid.uuid4()
OWNER = uuid.uuid4()
NOW = datetime.now(timezone.utc)


def _base(**kw):
    p = dict(org_id=ORG1, company_id=C1, name="会籍拓展商机A", owner_user_id=OWNER, stage="discovery")
    p.update(kw)
    return CrmOpportunity(**p)


def test_ac1_columns_and_roundtrip(migrated_engine):
    insp = inspect(migrated_engine)
    cols = {c["name"] for c in insp.get_columns("crm_opportunity")}
    assert {"id", "org_id", "company_id", "lead_id", "name", "owner_user_id", "stage",
            "stage_changed_at", "expected_first_year_amount_fen", "membership_tier", "space_type",
            "seats_needed", "area_sqm", "expected_move_in_date", "expected_close_date",
            "win_probability", "lost_reason", "closed_at", "merged_into_id"} <= cols


class TestAC2LostReasonCheck:
    def test_lost_without_reason_rejected(self, migrated_engine):
        with Session(migrated_engine) as s:
            s.add(_base(stage="lost", lost_reason=None))
            with pytest.raises(IntegrityError):
                s.commit()
            s.rollback()
            s.add(_base(stage="lost", lost_reason="price", closed_at=NOW))
            s.commit()

    def test_open_stage_allows_empty_reason(self, migrated_engine):
        with Session(migrated_engine) as s:
            s.add(_base(stage="discovery", lost_reason=None))
            s.commit()


class TestAC3AmountColumnAndCheck:
    def test_column_is_bigint(self, migrated_engine):
        insp = inspect(migrated_engine)
        col = next(c for c in insp.get_columns("crm_opportunity") if c["name"] == "expected_first_year_amount_fen")
        assert "BIGINT" in str(col["type"]).upper() or "INTEGER" in str(col["type"]).upper()

    def test_negative_amount_rejected(self, migrated_engine):
        with Session(migrated_engine) as s:
            s.add(_base(expected_first_year_amount_fen=-1))
            with pytest.raises(IntegrityError):
                s.commit()
            s.rollback()
            s.add(_base(expected_first_year_amount_fen=0))
            s.commit()


class TestAC4BackfillForeignKeys:
    def test_fks_exist_after_upgrade(self, migrated_engine):
        insp = inspect(migrated_engine)
        if migrated_engine.dialect.name == "postgresql":
            fks_int = {f["constrained_columns"][0]: f["referred_table"] for f in insp.get_foreign_keys("crm_interaction")}
            fks_lead = {f["constrained_columns"][0]: f["referred_table"] for f in insp.get_foreign_keys("crm_lead")}
            assert fks_int.get("opportunity_id") == "crm_opportunity"
            assert fks_lead.get("converted_opportunity_id") == "crm_opportunity"
        else:
            # SQLite：通过 PRAGMA 校验（引擎级别）
            from sqlalchemy import text
            with migrated_engine.connect() as conn:
                rows = conn.execute(text("PRAGMA foreign_key_list(crm_interaction)")).fetchall()
            m = {r[3]: r[2] for r in rows}
            assert m.get("opportunity_id") == "crm_opportunity"
            with migrated_engine.connect() as conn:
                rows = conn.execute(text("PRAGMA foreign_key_list(crm_lead)")).fetchall()
            m = {r[3]: r[2] for r in rows}
            assert m.get("converted_opportunity_id") == "crm_opportunity"


class TestEdgeCases:
    def test_win_probability_bounds(self, migrated_engine):
        with Session(migrated_engine) as s:
            s.add(_base(win_probability=101))
            with pytest.raises(IntegrityError):
                s.commit()
            s.rollback()
            s.add(_base(win_probability=-1))
            with pytest.raises(IntegrityError):
                s.commit()
            s.rollback()
            s.add(_base(win_probability=0))
            s.add(_base(win_probability=100))
            s.commit()

    def test_stage_enum(self, migrated_engine):
        with Session(migrated_engine) as s:
            s.add(_base(stage="frozen"))
            with pytest.raises(IntegrityError):
                s.commit()
            s.rollback()

    def test_membership_tier_enum(self, migrated_engine):
        with Session(migrated_engine) as s:
            s.add(_base(membership_tier="gold"))
            with pytest.raises(IntegrityError):
                s.commit()
            s.rollback()
            s.add(_base(membership_tier="strategic"))
            s.commit()

    def test_seats_and_area_nonneg(self, migrated_engine):
        with Session(migrated_engine) as s:
            s.add(_base(seats_needed=-2))
            with pytest.raises(IntegrityError):
                s.commit()
            s.rollback()
            s.add(_base(seats_needed=0, area_sqm=0))
            s.commit()

    def test_merged_into_self_reference(self, migrated_engine):
        with Session(migrated_engine) as s:
            a = _base(name="商机A")
            s.add(a)
            s.commit()
            b = _base(name="商机B", merged_into_id=a.id)
            s.add(b)
            s.commit()
            assert b.merged_into_id == a.id
