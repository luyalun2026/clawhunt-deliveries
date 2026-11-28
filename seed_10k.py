# -*- coding: utf-8 -*-
"""灌入 1 万条虚构互动记录（确定性伪随机，无真实信息）。用法：python seed_10k.py"""
import os
import random
import uuid
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from crm.models.interaction import CrmInteraction

random.seed(20261128)
TYPES = ["visit", "call", "wechat", "meeting", "event", "email", "other"]
SOURCES = ["manual", "import", "system"]

DSN = os.environ.get("PG_DSN") or "sqlite:///./seed_10k.db"
engine = create_engine(DSN)
org_id = uuid.uuid5(uuid.NAMESPACE_URL, "seed-org")
company_id = uuid.uuid5(uuid.NAMESPACE_URL, "seed-company")
base_time = datetime(2026, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

with Session(engine) as s:
    for i in range(10000):
        s.add(CrmInteraction(
            org_id=org_id,
            company_id=company_id,
            type=random.choice(TYPES),
            occurred_at=base_time + timedelta(minutes=i * 37),
            duration_minutes=random.randint(5, 120),
            summary=f"虚构纪要 {i}：例行接触与进展记录。",
            source=random.choice(SOURCES),
            owner_user_id=uuid.uuid5(uuid.NAMESPACE_URL, f"owner-{i % 20}"),
        ))
    s.commit()
print("seeded 10000 rows into", DSN)
