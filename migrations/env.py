import pathlib
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool
import sqlalchemy as sa

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from crm.models import Base  # noqa: E402

config = context.config
x_args = context.get_x_argument(as_dictionary=True)
if x_args.get("db_url"):
    config.set_main_option("sqlalchemy.url", x_args["db_url"])
if config.config_file_name is not None:
    fileConfig = None  # 不用日志配置，保持输出干净
target_metadata = Base.metadata


def _include_object(obj, name, type_, reflected, compare_to):
    # SQLite 反射不保留外键约束名，命名 FK 的元数据比对必然误报；
    # 外键一致性由 AC4 的 PRAGMA/反射断言显式覆盖（README 有说明）。
    if type_ == "foreign_key_constraint":
        return False
    # SQLite 反射丢弃 DESC 排序方向，表达式索引（occurred_at DESC）比对必然误报；
    # 表达式索引的存在性由反射断言与 EXPLAIN 实测显式覆盖。
    if type_ == "index" and any(
        isinstance(e, sa.sql.elements.TextClause) for e in obj.expressions
    ):
        return False
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=False,
        compare_server_default=False,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=False,
            compare_server_default=False,
            include_object=_include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
