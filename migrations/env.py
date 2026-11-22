# -*- coding: utf-8 -*-
"""Alembic env：target_metadata 绑定 models.Base.metadata。

连接串优先级：环境变量 IP_DB_URL > alembic.ini 的 sqlalchemy.url。
生产（PostgreSQL 16）示例：IP_DB_URL=postgresql+psycopg://user:pass@host:5432/db alembic upgrade head
"""
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

import models

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = models.Base.metadata


def _url() -> str:
    return os.environ.get("IP_DB_URL") or config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    url = _url()
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = _url()
    config.set_main_option("sqlalchemy.url", url)
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
