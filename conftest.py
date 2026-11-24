# -*- coding: utf-8 -*-
"""测试夹具：临时库 + CRM 接口桩 + 固定时钟。"""
import os
import sys
from datetime import datetime, timezone

import pytest

PKG = os.path.dirname(os.path.abspath(__file__))
if PKG not in sys.path:
    sys.path.insert(0, PKG)

from app.attribution import AttributionService   # noqa: E402
from app.crm_stub import CrmStub                  # noqa: E402
from app.db import init_db                        # noqa: E402

BASE = datetime(2026, 11, 15, 10, 0, 0, tzinfo=timezone.utc)


def make_report(reporter_id="CH-001", name="武汉虚构科技有限公司",
                uscc="91420100MA4K000001", phone="13800138000", **extra):
    payload = {"reporter_type": "channel", "reporter_id": reporter_id,
               "company_name": name, "uscc": uscc, "contact_phone": phone,
               "org_id": "org-demo", "site_id": "site-a"}
    payload.update(extra)
    return payload


@pytest.fixture
def svc(tmp_path):
    db_path = str(tmp_path / "attribution.db")
    init_db(db_path)
    crm = CrmStub()
    return AttributionService(db_path, crm=crm, salt="test-salt")
