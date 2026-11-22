# -*- coding: utf-8 -*-
"""测试公共夹具与工具。"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import clock  # noqa: E402
from app.main import create_app  # noqa: E402

ESIGN_SECRET = "unit-test-esign-secret"
PRESIGN_SECRET = "unit-test-presign-secret"


@pytest.fixture(autouse=True)
def _reset_clock():
    clock.reset()
    yield
    clock.reset()


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app, monkeypatch):
    monkeypatch.setenv("ESIGN_SECRET", ESIGN_SECRET)
    monkeypatch.setenv("PRESIGN_SECRET", PRESIGN_SECRET)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db(app):
    return app.state.db
