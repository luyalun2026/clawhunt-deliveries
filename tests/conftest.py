# -*- coding: utf-8 -*-
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from service import Service  # noqa: E402


@pytest.fixture()
def svc():
    return Service()


@pytest.fixture(scope="session")
def matrix():
    with open(os.path.join(ROOT, "access_matrix.yaml"), encoding="utf-8") as f:
        return json.load(f)
