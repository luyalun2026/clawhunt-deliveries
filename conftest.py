# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from app.policy import load_rules, make_router
from app.refusal import decide
from app.settings import Settings
from stub.gap_service import GapRecorder
from stub.generator import Generator


@pytest.fixture(scope="session")
def rules():
    return load_rules()


@pytest.fixture()
def router(rules):
    return make_router(rules)


@pytest.fixture()
def settings():
    return Settings(min_rerank_score=0.35, min_evidence=1, doc_freshness_days=180)


@pytest.fixture()
def gap():
    return GapRecorder()


@pytest.fixture()
def gen():
    return Generator()


def _chunk(cid, score=0.9, text="独立办公室按面积每月计价，最小工位 6 个起。", site="S1",
          valid_until="2099-01-01", deleted=None, classification=1):
    return {"chunk_id": cid, "text": text, "rerank_score": score, "site_id": site,
            "doc_review_valid_until": valid_until, "deleted_at": deleted,
            "classification": classification}


@pytest.fixture()
def chunk():
    return _chunk


@pytest.fixture()
def ask(router, gap):
    def _ask(question, chunks, gen, settings=Settings(min_rerank_score=0.35, min_evidence=1),
             site_id="S1", user_level=2, today=None):
        return decide(question, chunks, site_id=site_id, settings=settings, policy_router=router,
                      gap=gap, generator=gen, user_level=user_level, today=today)
    return _ask
