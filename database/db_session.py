import asyncio
from contextlib import asynccontextmanager
from typing import Any
from weakref import WeakSet

import config
from config.db_config import sqlite_db_config
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from .models import Base

_engines = {}
_schema_lock = asyncio.Lock()
_initialized_schema_engines = WeakSet()

_BUSINESS_KEYS = (
    ("xhs_note", "note_id", "ux_xhs_note_note_id"),
    ("xhs_note_comment", "comment_id", "ux_xhs_note_comment_comment_id"),
    ("xhs_creator", "user_id", "ux_xhs_creator_user_id"),
)


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
    if engine in _initialized_schema_engines:
        return
    async with _schema_lock:
        if engine in _initialized_schema_engines:
            return
        async with engine.begin() as conn:
            await conn.exec_driver_sql("PRAGMA journal_mode=WAL")
            await conn.exec_driver_sql("PRAGMA busy_timeout=5000")
            await conn.exec_driver_sql("PRAGMA foreign_keys=ON")

            # Existing installations predate the business-key constraints. Merge
            # duplicate rows before SQLAlchemy attempts to create unique indexes.
            for table_name, key_name, index_name in _BUSINESS_KEYS:
                if await _table_exists(conn, table_name):
                    await _merge_duplicate_business_keys(conn, table_name, key_name)
                    await _ensure_unique_business_index(conn, table_name, key_name, index_name)

            await conn.run_sync(Base.metadata.create_all)

            # New and partially migrated databases both end up with the same
            # invariant, even when an old non-unique SQLAlchemy index exists.
            for table_name, key_name, index_name in _BUSINESS_KEYS:
                await _ensure_unique_business_index(conn, table_name, key_name, index_name)
        _initialized_schema_engines.add(engine)


async def _table_exists(conn, table_name: str) -> bool:
    result = await conn.exec_driver_sql(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return result.first() is not None


async def _ensure_unique_business_index(
    conn,
    table_name: str,
    key_name: str,
    index_name: str,
) -> None:
    indexes = (await conn.exec_driver_sql(f'PRAGMA index_list("{table_name}")')).mappings().all()
    for index in indexes:
        if not index.get("unique"):
            continue
        existing_name = str(index["name"]).replace('"', '""')
        columns = (
            await conn.exec_driver_sql(f'PRAGMA index_info("{existing_name}")')
        ).mappings().all()
        if [column["name"] for column in columns] == [key_name]:
            return

    await conn.exec_driver_sql(
        f'CREATE UNIQUE INDEX IF NOT EXISTS "{index_name}" '
        f'ON "{table_name}" ("{key_name}")'
    )


async def _merge_duplicate_business_keys(conn, table_name: str, key_name: str) -> None:
    duplicate_keys = (
        await conn.exec_driver_sql(
            f'SELECT "{key_name}" FROM "{table_name}" '
            f'WHERE "{key_name}" IS NOT NULL GROUP BY "{key_name}" HAVING COUNT(*) > 1'
        )
    ).scalars().all()

    for business_key in duplicate_keys:
        rows = (
            await conn.exec_driver_sql(
                f'SELECT * FROM "{table_name}" WHERE "{key_name}" = ? '
                "ORDER BY COALESCE(last_modify_ts, 0) DESC, id DESC",
                (business_key,),
            )
        ).mappings().all()
        if len(rows) < 2:
            continue

        survivor = dict(rows[0])
        update_values = {}
        for column_name, current_value in survivor.items():
            if column_name in {"id", key_name} or _db_value_present(current_value):
                continue
            replacement = next(
                (
                    row[column_name]
                    for row in rows[1:]
                    if _db_value_present(row[column_name])
                ),
                None,
            )
            if replacement is not None:
                update_values[column_name] = replacement

        if update_values:
            assignments = ", ".join(f'"{column}"=?' for column in update_values)
            await conn.exec_driver_sql(
                f'UPDATE "{table_name}" SET {assignments} WHERE id=?',
                (*update_values.values(), survivor["id"]),
            )

        duplicate_ids = [row["id"] for row in rows[1:]]
        placeholders = ",".join("?" for _ in duplicate_ids)
        await conn.exec_driver_sql(
            f'DELETE FROM "{table_name}" WHERE id IN ({placeholders})',
            tuple(duplicate_ids),
        )


def _db_value_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() not in {"", "none", "null", '""', "[]", "{}"}
    return True


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
