# -*- coding: utf-8 -*-
"""按 company_id 取最近 20 条的 EXPLAIN(ANALYZE)，断言命中 ix_int_org_company_occ。用法：python explain_query.py"""
import json
import os
import uuid

from sqlalchemy import create_engine, text

DSN = os.environ.get("PG_DSN")
assert DSN, "explain_query.py 需要真实 PG16（设置 PG_DSN；SQLite 无 EXPLAIN 索引选择语义）"
engine = create_engine(DSN)
org_id = uuid.uuid5(uuid.NAMESPACE_URL, "seed-org")
company_id = uuid.uuid5(uuid.NAMESPACE_URL, "seed-company")
sql = text(
    "EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM crm_interaction "
    "WHERE org_id = :o AND company_id = :c AND deleted_at IS NULL "
    "ORDER BY occurred_at DESC LIMIT 20"
)
with engine.connect() as conn:
    plan = conn.execute(sql, {"o": org_id, "c": company_id}).fetchall()
lines = [r[0] for r in plan]
out = "\n".join(lines)
print(out)
assert "ix_int_org_company_occ" in out, "未命中复合索引 ix_int_org_company_occ"
open("outputs/explain-output.txt", "w", encoding="utf-8").write(out + "\n")
print("INDEX HIT OK → outputs/explain-output.txt")
