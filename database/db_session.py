from contextlib import asynccontextmanager

import config
from config.db_config import sqlite_db_config
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from .models import Base

_engines = {}


def get_async_engine(db_type: str = None):
    db_type = db_type or config.SAVE_DATA_OPTION
    if db_type != "sqlite":
        raise ValueError(f"Unsupported database type for this service: {db_type}")

    if db_type not in _engines:
        db_url = f"sqlite+aiosqlite:///{sqlite_db_config['db_path']}"
        _engines[db_type] = create_async_engine(
            db_url,
            echo=False,
            connect_args={"timeout": 5},
        )
    return _engines[db_type]


async def create_tables(db_type: str = None):
    engine = get_async_engine(db_type or "sqlite")
    async with engine.begin() as conn:
        await conn.exec_driver_sql("PRAGMA journal_mode=WAL")
        await conn.exec_driver_sql("PRAGMA busy_timeout=5000")
        await conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_session() -> AsyncSession:
    engine = get_async_engine("sqlite")
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
