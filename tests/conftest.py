"""pytest 共享夹具：临时 SQLite、TestClient、合法载荷。"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

# 必须在导入 app 之前设置环境变量（config.py 在导入时读取）
_tmpdir = tempfile.mkdtemp(prefix="ch2154_")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_tmpdir) / 'test.db'}"
os.environ["REVIEW_SERVICE_KEYS"] = "svc-test-key,svc-other-key"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402

HEADERS = {"X-Service-Key": "svc-test-key"}


def make_payload(**overrides):
    payload = {
        "feature_code": "crm.opportunity.summary",
        "source_type": "crm_opportunity",
        "source_id": "opp-1001",
        "title": "会员空间平台商机摘要草稿",
        "ai_content": {
            "summary": "某会员企业希望对接园区财税服务商",
            "keywords": ["财税", "服务商对接"],
            "confidence_score": 0.9,
        },
        "schema_id": "member_space.chat_summary",
        "schema_version": "1.0",
        "gw_request_id": "gw-req-0001",
        "drafter_id": "drafter-001",
        "requested_level": "standard",
        "org_id": "org-1",
        "site_id": "site-1",
    }
    payload.update(overrides)
    return payload


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def client(create_tables):
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def session():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()
