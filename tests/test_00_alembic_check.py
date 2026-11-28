"""AC1（前半）：alembic check 零漂移——模型元数据与迁移后的库完全一致。"""
import pytest
from alembic import command
from sqlalchemy import create_engine, inspect


def test_alembic_check_zero_drift(migrated_engine, tmp_path):
    insp = inspect(migrated_engine)
    assert "crm_opportunity" in insp.get_table_names()
    from conftest import make_cfg

    cfg, url = make_cfg(tmp_path / "chk.sqlite")
    command.upgrade(cfg, "head")
    try:
        command.check(cfg)
    finally:
        command.downgrade(cfg, "base")
