# -*- coding: utf-8 -*-
import json
import os
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional

import aiosqlite

from config.settings import settings
from config.db_config import SQLITE_DB_PATH

SERVICE_DB_PATH = settings.service_db_path


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskType(str, Enum):
    SEARCH = "search"
    CREATOR = "creator"
    NOTE = "note"


class AccountStatus(str, Enum):
    ACTIVE = "active"
    CAPTCHA = "captcha"
    COOLING_DOWN = "cooling_down"
    INVALID = "invalid"


ACTIVE_TASK_STATUSES = (
    TaskStatus.PENDING.value,
    TaskStatus.RUNNING.value,
    TaskStatus.PAUSED.value,
)

_TASK_UPDATE_FIELDS = {
    "status",
    "params",
    "started_at",
    "completed_at",
    "error",
    "notes_count",
    "comments_count",
    "progress",
    "progress_data",
    "task_key",
    "lease_owner",
    "heartbeat_at",
    "lease_expires_at",
}

_ACCOUNT_UPDATE_FIELDS = {
    "name",
    "cookie",
    "status",
    "captcha_count",
    "last_checked",
}


def _now() -> str:
    return datetime.now().isoformat()


def _task_status_value(status: TaskStatus | str) -> str:
    return status.value if isinstance(status, TaskStatus) else status


def _task_type_value(task_type: TaskType | str) -> str:
    return task_type.value if isinstance(task_type, TaskType) else task_type


def _account_status_value(status: AccountStatus | str) -> str:
    return status.value if isinstance(status, AccountStatus) else status


def task_dedupe_key(task_type: TaskType | str, params: Dict) -> str:
    """Stable key used to collapse duplicate active task submissions."""
    return (
        f"{_task_type_value(task_type)}:"
        f"{json.dumps(params, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}"
    )


def _encode_progress_data(
    *,
    stage: Optional[str] = None,
    message: Optional[str] = None,
    notes_count: Optional[int] = None,
    comments_count: Optional[int] = None,
    updated_at: Optional[str] = None,
) -> str:
    return json.dumps(
        {
            "stage": stage,
            "message": message,
            "notes_count": notes_count,
            "comments_count": comments_count,
            "updated_at": updated_at or _now(),
        },
        ensure_ascii=False,
    )


def _decode_task_row(row) -> Dict:
    task = dict(row)
    raw = task.get("progress_data")
    if raw:
        try:
            task["progress_data"] = json.loads(raw)
        except json.JSONDecodeError:
            task["progress_data"] = None
    else:
        task["progress_data"] = None
    return task


async def _ensure_column(db: aiosqlite.Connection, table: str, column: str, definition: str):
    cursor = await db.execute(f"PRAGMA table_info({table})")
    rows = await cursor.fetchall()
    if column not in {row[1] for row in rows}:
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


async def _configure_sqlite(db: aiosqlite.Connection):
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA busy_timeout=5000")
    await db.execute("PRAGMA foreign_keys=ON")


async def init_service_db():
    os.makedirs(os.path.dirname(SERVICE_DB_PATH), exist_ok=True)
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        await _configure_sqlite(db)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                task_type   TEXT    NOT NULL,
                params      TEXT    NOT NULL,
                status      TEXT    NOT NULL DEFAULT 'pending',
                created_at  TEXT    NOT NULL,
                started_at  TEXT,
                completed_at TEXT,
                error       TEXT,
                notes_count INTEGER DEFAULT 0,
                comments_count INTEGER DEFAULT 0,
                progress    TEXT,
                progress_data TEXT,
                task_key    TEXT,
                lease_owner TEXT,
                heartbeat_at TEXT,
                lease_expires_at TEXT
            )
        """)
        await _ensure_column(db, "tasks", "task_key", "TEXT")
        await _ensure_column(db, "tasks", "lease_owner", "TEXT")
        await _ensure_column(db, "tasks", "heartbeat_at", "TEXT")
        await _ensure_column(db, "tasks", "lease_expires_at", "TEXT")
        await _ensure_column(db, "tasks", "progress_data", "TEXT")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_tasks_task_key_status ON tasks(task_key, status)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status_created ON tasks(status, created_at)")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS note_tags (
                note_id   TEXT PRIMARY KEY,
                d_level   TEXT NOT NULL,
                quality   TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                cookie        TEXT NOT NULL,
                status        TEXT NOT NULL DEFAULT 'active',
                captcha_count INTEGER DEFAULT 0,
                last_checked  TEXT,
                created_at    TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS crawl_events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at  TEXT NOT NULL,
                event_type  TEXT NOT NULL,
                account_id  INTEGER,
                task_id     INTEGER,
                endpoint    TEXT,
                error_type  TEXT,
                message     TEXT
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_crawl_events_type_time ON crawl_events(event_type, created_at)")
        await db.commit()


async def upsert_note_tag(note_id: str, d_level: str, quality: str):
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        await db.execute(
            "INSERT INTO note_tags (note_id, d_level, quality, updated_at) VALUES (?,?,?,?) "
            "ON CONFLICT(note_id) DO UPDATE SET d_level=excluded.d_level, quality=excluded.quality, updated_at=excluded.updated_at",
            (note_id, d_level, quality, _now()),
        )
        await db.commit()


async def get_all_note_tags() -> Dict:
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT note_id, d_level, quality FROM note_tags")
        rows = await cursor.fetchall()
    return {r["note_id"]: {"d_level": r["d_level"], "quality": r["quality"]} for r in rows}


async def create_task(task_type: TaskType | str, params: Dict, dedupe: bool = True) -> int:
    task_type_value = _task_type_value(task_type)
    task_key = task_dedupe_key(task_type_value, params)
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        if dedupe:
            cursor = await db.execute(
                "SELECT id FROM tasks WHERE task_type=? AND task_key=? AND status IN (?, ?, ?) "
                "ORDER BY created_at ASC LIMIT 1",
                (task_type_value, task_key, *ACTIVE_TASK_STATUSES),
            )
            row = await cursor.fetchone()
            if row:
                await db.commit()
                return row[0]
        cursor = await db.execute(
            "INSERT INTO tasks (task_type, params, status, created_at, task_key) VALUES (?, ?, ?, ?, ?)",
            (
                task_type_value,
                json.dumps(params, ensure_ascii=False),
                TaskStatus.PENDING.value,
                _now(),
                task_key,
            ),
        )
        await db.commit()
        return cursor.lastrowid


async def update_task_status(task_id: int, status: TaskStatus | str, **kwargs):
    unknown_fields = set(kwargs) - _TASK_UPDATE_FIELDS
    if unknown_fields:
        raise ValueError(f"Unknown task fields: {sorted(unknown_fields)}")
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        fields = ["status = ?"]
        values = [_task_status_value(status)]
        for k, v in kwargs.items():
            fields.append(f"{k} = ?")
            values.append(v)
        values.append(task_id)
        await db.execute(
            f"UPDATE tasks SET {', '.join(fields)} WHERE id = ?",
            values,
        )
        await db.commit()


async def update_task_status_if_owned(
    task_id: int,
    lease_owner: str,
    status: TaskStatus | str,
    **kwargs,
) -> bool:
    unknown_fields = set(kwargs) - _TASK_UPDATE_FIELDS
    if unknown_fields:
        raise ValueError(f"Unknown task fields: {sorted(unknown_fields)}")
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        fields = ["status = ?"]
        values = [_task_status_value(status)]
        for k, v in kwargs.items():
            fields.append(f"{k} = ?")
            values.append(v)
        values.extend([task_id, lease_owner])
        cursor = await db.execute(
            f"UPDATE tasks SET {', '.join(fields)} WHERE id = ? AND lease_owner = ?",
            values,
        )
        await db.commit()
        return cursor.rowcount == 1


async def claim_task(task_id: int, lease_owner: str, lease_seconds: int = 300) -> bool:
    now = _now()
    lease_expires_at = (datetime.now() + timedelta(seconds=lease_seconds)).isoformat()
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE tasks SET status=?, started_at=COALESCE(started_at, ?), "
            "lease_owner=?, heartbeat_at=?, lease_expires_at=? WHERE id=? AND "
            "(status=? OR (status=? AND (lease_expires_at IS NULL OR lease_expires_at < ?)) "
            "OR (status=? AND (lease_expires_at IS NULL OR lease_expires_at < ?)))",
            (
                TaskStatus.RUNNING.value,
                now,
                lease_owner,
                now,
                lease_expires_at,
                task_id,
                TaskStatus.PENDING.value,
                TaskStatus.RUNNING.value,
                now,
                TaskStatus.PAUSED.value,
                now,
            ),
        )
        await db.commit()
        return cursor.rowcount == 1


async def heartbeat_task(
    task_id: int,
    lease_owner: str,
    lease_seconds: int = 300,
    progress: Optional[str] = None,
    notes_count: Optional[int] = None,
    comments_count: Optional[int] = None,
    stage: Optional[str] = None,
    message: Optional[str] = None,
):
    now = _now()
    lease_expires_at = (datetime.now() + timedelta(seconds=lease_seconds)).isoformat()
    fields = ["heartbeat_at=?", "lease_expires_at=?"]
    values = [now, lease_expires_at]
    if progress is not None:
        fields.append("progress=?")
        values.append(progress)
    if notes_count is not None:
        fields.append("notes_count=?")
        values.append(notes_count)
    if comments_count is not None:
        fields.append("comments_count=?")
        values.append(comments_count)
    if any(v is not None for v in (stage, message, notes_count, comments_count)):
        fields.append("progress_data=?")
        values.append(
            _encode_progress_data(
                stage=stage,
                message=message if message is not None else progress,
                notes_count=notes_count,
                comments_count=comments_count,
                updated_at=now,
            )
        )
    values.extend([task_id, lease_owner])
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        cursor = await db.execute(
            f"UPDATE tasks SET {', '.join(fields)} WHERE id=? AND lease_owner=?",
            values,
        )
        await db.commit()
        return cursor.rowcount == 1


async def release_task_lease(task_id: int, lease_owner: str):
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        await db.execute(
            "UPDATE tasks SET lease_owner=NULL, lease_expires_at=NULL WHERE id=? AND lease_owner=?",
            (task_id, lease_owner),
        )
        await db.commit()


async def get_task(task_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
        return _decode_task_row(row) if row else None


async def reset_task_for_resume(task_id: int, new_params: Dict):
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        cursor = await db.execute("SELECT task_type FROM tasks WHERE id=?", (task_id,))
        row = await cursor.fetchone()
        task_type = row[0] if row else TaskType.SEARCH.value
        # Keep existing notes_count/comments_count so history is visible while pending.
        await db.execute(
            "UPDATE tasks SET status=?, params=?, task_key=?, started_at=NULL, completed_at=NULL, "
            "error=NULL, progress='resume queued', progress_data=?, lease_owner=NULL, heartbeat_at=NULL, lease_expires_at=NULL "
            "WHERE id=?",
            (
                TaskStatus.PENDING.value,
                json.dumps(new_params, ensure_ascii=False),
                task_dedupe_key(task_type, new_params),
                _encode_progress_data(stage="pending", message="resume queued"),
                task_id,
            ),
        )
        await db.commit()


async def requeue_unfinished_tasks() -> List[int]:
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "UPDATE tasks SET status=?, started_at=NULL, progress='requeued', progress_data=?, "
            "lease_owner=NULL, heartbeat_at=NULL, lease_expires_at=NULL WHERE status IN (?, ?)",
            (
                TaskStatus.PENDING.value,
                _encode_progress_data(stage="pending", message="requeued"),
                TaskStatus.RUNNING.value,
                TaskStatus.PAUSED.value,
            ),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT id FROM tasks WHERE status=? ORDER BY created_at ASC",
            (TaskStatus.PENDING.value,),
        )
        rows = await cursor.fetchall()
    return [r["id"] for r in rows]


async def pause_unfinished_tasks(progress: str = "waiting for account pool recovery") -> List[int]:
    progress_data = _encode_progress_data(stage="paused", message=progress)
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "UPDATE tasks SET status=?, progress=?, progress_data=?, "
            "lease_owner=NULL, heartbeat_at=NULL, lease_expires_at=NULL "
            "WHERE status IN (?, ?, ?)",
            (
                TaskStatus.PAUSED.value,
                progress,
                progress_data,
                TaskStatus.PENDING.value,
                TaskStatus.RUNNING.value,
                TaskStatus.PAUSED.value,
            ),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT id FROM tasks WHERE status=? ORDER BY created_at ASC",
            (TaskStatus.PAUSED.value,),
        )
        rows = await cursor.fetchall()
    return [r["id"] for r in rows]


async def list_paused_task_ids(limit: int = 100) -> List[int]:
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id FROM tasks WHERE status=? AND lease_owner IS NULL ORDER BY created_at ASC LIMIT ?",
            (TaskStatus.PAUSED.value, limit),
        )
        rows = await cursor.fetchall()
    return [r["id"] for r in rows]


async def list_expired_running_task_ids(limit: int = 100) -> List[int]:
    now = _now()
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id FROM tasks WHERE status=? AND "
            "(lease_expires_at IS NULL OR lease_expires_at < ?) "
            "ORDER BY created_at ASC LIMIT ?",
            (TaskStatus.RUNNING.value, now, limit),
        )
        rows = await cursor.fetchall()
    return [r["id"] for r in rows]


async def pause_expired_running_tasks(progress: str = "waiting for account pool recovery") -> List[int]:
    now = _now()
    progress_data = _encode_progress_data(stage="paused", message=progress, updated_at=now)
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id FROM tasks WHERE status=? AND "
            "(lease_expires_at IS NULL OR lease_expires_at < ?) "
            "ORDER BY created_at ASC",
            (TaskStatus.RUNNING.value, now),
        )
        rows = await cursor.fetchall()
        ids = [r["id"] for r in rows]
        if ids:
            placeholders = ",".join("?" for _ in ids)
            await db.execute(
                f"UPDATE tasks SET status=?, progress=?, progress_data=?, "
                "lease_owner=NULL, heartbeat_at=NULL, lease_expires_at=NULL "
                f"WHERE id IN ({placeholders})",
                (TaskStatus.PAUSED.value, progress, progress_data, *ids),
            )
            await db.commit()
    return ids


async def find_latest_search_task(keyword: str) -> Optional[Dict]:
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM tasks WHERE task_type=? AND json_extract(params,'$.keyword')=? ORDER BY created_at DESC LIMIT 1",
            (TaskType.SEARCH.value, keyword),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def find_latest_creator_task(creator_input: str) -> Optional[Dict]:
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM tasks WHERE task_type=? AND json_extract(params,'$.creator_input')=? ORDER BY created_at DESC LIMIT 1",
            (TaskType.CREATOR.value, creator_input),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def list_tasks(limit: int = 100) -> List[Dict]:
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return [_decode_task_row(r) for r in rows]


def _task_params(task: Dict) -> Dict:
    raw = task.get("params") or "{}"
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}


async def enrich_tasks_with_crawl_counts(tasks: List[Dict]) -> List[Dict]:
    """Overlay task rows with live crawl totals from the XHS data DB."""
    if not tasks or not os.path.exists(SQLITE_DB_PATH):
        return tasks

    async with aiosqlite.connect(SQLITE_DB_PATH) as db:
        for task in tasks:
            params = _task_params(task)
            if task.get("task_type") == TaskType.SEARCH.value:
                keyword = params.get("keyword")
                if not keyword:
                    continue
                cur = await db.execute(
                    "SELECT COUNT(DISTINCT note_id) FROM xhs_note WHERE source_keyword=?",
                    (keyword,),
                )
                row = await cur.fetchone()
                notes_count = row[0] if row else 0
                cur = await db.execute(
                    "SELECT COUNT(*) FROM xhs_note_comment WHERE note_id IN "
                    "(SELECT note_id FROM xhs_note WHERE source_keyword=?)",
                    (keyword,),
                )
                row = await cur.fetchone()
                comments_count = row[0] if row else 0
            elif task.get("task_type") == TaskType.CREATOR.value:
                user_id = params.get("user_id") or params.get("creator_input")
                if not user_id:
                    continue
                cur = await db.execute(
                    "SELECT COUNT(DISTINCT note_id) FROM xhs_note WHERE user_id=?",
                    (user_id,),
                )
                row = await cur.fetchone()
                notes_count = row[0] if row else 0
                cur = await db.execute(
                    "SELECT COUNT(*) FROM xhs_note_comment WHERE note_id IN "
                    "(SELECT note_id FROM xhs_note WHERE user_id=?)",
                    (user_id,),
                )
                row = await cur.fetchone()
                comments_count = row[0] if row else 0
            else:
                continue

            task["notes_count"] = notes_count
            task["comments_count"] = comments_count
            progress_data = task.get("progress_data")
            if isinstance(progress_data, dict):
                progress_data.setdefault("notes_count", notes_count)
                progress_data.setdefault("comments_count", comments_count)
    return tasks


async def add_account(name: str, cookie: str) -> int:
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO accounts (name, cookie, status, created_at) VALUES (?,?,?,?)",
            (name, cookie, AccountStatus.ACTIVE.value, _now()),
        )
        await db.commit()
        return cursor.lastrowid


async def update_account(account_id: int, **kwargs):
    if not kwargs:
        return
    unknown_fields = set(kwargs) - _ACCOUNT_UPDATE_FIELDS
    if unknown_fields:
        raise ValueError(f"Unknown account fields: {sorted(unknown_fields)}")
    if "status" in kwargs:
        kwargs["status"] = _account_status_value(kwargs["status"])
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        fields = [f"{k} = ?" for k in kwargs]
        values = list(kwargs.values()) + [account_id]
        await db.execute(
            f"UPDATE accounts SET {', '.join(fields)} WHERE id = ?", values
        )
        await db.commit()


async def list_accounts() -> List[Dict]:
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM accounts ORDER BY id")
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_account(account_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
        row = await cursor.fetchone()
    return dict(row) if row else None


async def delete_account(account_id: int):
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        await db.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        await db.commit()


async def get_active_accounts() -> List[Dict]:
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM accounts WHERE status=? ORDER BY id",
            (AccountStatus.ACTIVE.value,),
        )
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def add_crawl_event(
    event_type: str,
    *,
    account_id: Optional[int] = None,
    task_id: Optional[int] = None,
    endpoint: Optional[str] = None,
    error_type: Optional[str] = None,
    message: Optional[str] = None,
) -> int:
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO crawl_events "
            "(created_at, event_type, account_id, task_id, endpoint, error_type, message) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (_now(), event_type, account_id, task_id, endpoint, error_type, message),
        )
        await db.commit()
        return cursor.lastrowid


async def count_recent_crawl_events(event_types: List[str], since_iso: str) -> int:
    if not event_types:
        return 0
    placeholders = ",".join("?" for _ in event_types)
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        cursor = await db.execute(
            f"SELECT COUNT(*) FROM crawl_events WHERE event_type IN ({placeholders}) AND created_at >= ?",
            (*event_types, since_iso),
        )
        row = await cursor.fetchone()
    return row[0] if row else 0


async def list_recent_crawl_events(limit: int = 50) -> List[Dict]:
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM crawl_events ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]
