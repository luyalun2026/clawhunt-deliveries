import pathlib

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

ROOT = pathlib.Path(__file__).resolve().parent


def make_cfg(db_path: pathlib.Path):
    url = "sqlite:///" + str(db_path).replace("\\", "/")
    if __import__("os").environ.get("PG_DSN"):
        url = __import__("os").environ["PG_DSN"]
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg, url


@pytest.fixture()
def migrated_engine(tmp_path):
    cfg, url = make_cfg(tmp_path / "db.sqlite")
    engine = create_engine(url)
    command.upgrade(cfg, "head")
    yield engine
    command.downgrade(cfg, "base")
    engine.dispose()
