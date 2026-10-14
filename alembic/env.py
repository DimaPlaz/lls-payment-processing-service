import asyncio
from logging.config import fileConfig

import sqlalchemy.ext.asyncio as sqlalchemyio
from sqlalchemy import pool
from sqlalchemy.engine import Connection

from alembic import context

from payments.infrastructure.database import base
from payments.infrastructure import settings

from payments.infrastructure.database.orm import Payment  # noqa: init orm model

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = base.Base.metadata


def get_url() -> str:
    # If alembic.ini has sqlalchemy.url set explicitly – use it.
    url = config.get_main_option("sqlalchemy.url")
    if url and "driver://" not in url:
        return url
    # Fallback to app settings (DB_ env-vars supported via db_settings)
    return str(settings.db.dsn)


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable: sqlalchemyio.AsyncEngine = sqlalchemyio.create_async_engine(
        get_url(),
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
