# -*- coding: utf-8 -*-
import json
import os
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional

import aiosqlite

from config.settings import settings
from config.db_config import SQLITE_DB_PATH

from .providers.justoneapi.options import TASK_OPTION_DEFAULTS

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


class TaskProvider(str, Enum):
    LOCAL = "local"
    JUSTONEAPI = "justoneapi"


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
    "checkpoint_json",
    "result_data",
    "retry_at",
    "attempt_count",
    "manual_resume_required",
}

_ACCOUNT_UPDATE_FIELDS = {
    "name",
    "cookie",
    "proxy_id",
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


def _task_provider_value(provider: TaskProvider | str) -> str:
    return provider.value if isinstance(provider, TaskProvider) else provider


def _account_status_value(status: AccountStatus | str) -> str:
    return status.value if isinstance(status, AccountStatus) else status


def task_dedupe_key(
    task_type: TaskType | str,
    params: Dict,
    provider: TaskProvider | str = TaskProvider.LOCAL,
) -> str:
    """Stable key used to collapse duplicate active task submissions."""
    return (
        f"{_task_provider_value(provider)}:{_task_type_value(task_type)}:"
        f"{json.dumps(params, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}"
    )


def task_scope_key(
    task_type: TaskType | str,
    params: Dict,
    provider: TaskProvider | str,
) -> str:
    task_type_value = _task_type_value(task_type)
    provider_value = _task_provider_value(provider)
    if provider_value == TaskProvider.LOCAL.value:
        identity = {
            "keyword": params.get("keyword"),
            "creator_input": params.get("creator_input"),
        }
    else:
        options = params.get("provider_options")
        options = options if isinstance(options, dict) else {}
        identity = {
            "keyword": params.get("keyword"),
            "creator_input": params.get("creator_input"),
            "sort_type": params.get("sort_type"),
            "include_details": options.get(
                "include_details",
                TASK_OPTION_DEFAULTS.include_details,
            ),
            "include_comments": options.get(
                "include_comments",
                TASK_OPTION_DEFAULTS.include_comments,
            ),
            "include_replies": options.get(
                "include_replies",
                TASK_OPTION_DEFAULTS.include_replies,
            ),
            "note_type": options.get("note_type", TASK_OPTION_DEFAULTS.note_type),
            "time_filter": options.get(
                "time_filter",
                TASK_OPTION_DEFAULTS.time_filter,
            ),
        }
    return (
        f"{provider_value}:{task_type_value}:"
        f"{json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(',', ':'))}"
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
    for field in ("progress_data", "checkpoint_json", "result_data"):
        raw = task.get(field)
        if raw:
            try:
                task[field] = json.loads(raw)
            except json.JSONDecodeError:
                task[field] = None
        else:
            task[field] = None
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
                provider    TEXT    NOT NULL DEFAULT 'local',
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
                lease_expires_at TEXT,
                checkpoint_json TEXT,
                result_data TEXT,
                retry_at TEXT,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                manual_resume_required INTEGER NOT NULL DEFAULT 0
            )
        """)
        await _ensure_column(db, "tasks", "provider", "TEXT NOT NULL DEFAULT 'local'")
        await _ensure_column(db, "tasks", "task_key", "TEXT")
        await _ensure_column(db, "tasks", "lease_owner", "TEXT")
        await _ensure_column(db, "tasks", "heartbeat_at", "TEXT")
        await _ensure_column(db, "tasks", "lease_expires_at", "TEXT")
        await _ensure_column(db, "tasks", "progress_data", "TEXT")
        await _ensure_column(db, "tasks", "checkpoint_json", "TEXT")
        await _ensure_column(db, "tasks", "result_data", "TEXT")
        await _ensure_column(db, "tasks", "retry_at", "TEXT")
        await _ensure_column(db, "tasks", "attempt_count", "INTEGER NOT NULL DEFAULT 0")
        await _ensure_column(
            db,
            "tasks",
            "manual_resume_required",
            "INTEGER NOT NULL DEFAULT 0",
        )
        await db.execute(
            "UPDATE tasks SET provider=? WHERE provider IS NULL OR provider=''",
            (TaskProvider.LOCAL.value,),
        )
        await db.execute(
            "UPDATE tasks SET task_key=provider || ':' || task_key "
            "WHERE task_key IS NOT NULL "
            "AND task_key NOT LIKE 'local:%' "
            "AND task_key NOT LIKE 'justoneapi:%'"
        )
        await db.execute("CREATE INDEX IF NOT EXISTS idx_tasks_task_key_status ON tasks(task_key, status)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status_created ON tasks(status, created_at)")
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_provider_status_retry "
            "ON tasks(provider, status, retry_at, created_at)"
        )
        await db.execute("""
            CREATE TABLE IF NOT EXISTS provider_requests (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id       INTEGER NOT NULL,
                provider      TEXT NOT NULL,
                endpoint      TEXT NOT NULL,
                request_id    TEXT,
                http_status   INTEGER,
                business_code INTEGER,
                duration_ms   INTEGER,
                attempt       INTEGER NOT NULL DEFAULT 1,
                billed        INTEGER NOT NULL DEFAULT 0,
                error_type    TEXT,
                request_state TEXT NOT NULL DEFAULT 'completed',
                outcome_unknown INTEGER NOT NULL DEFAULT 0,
                created_at    TEXT NOT NULL
            )
        """)
        await _ensure_column(db, "provider_requests", "error_type", "TEXT")
        await _ensure_column(
            db,
            "provider_requests",
            "request_state",
            "TEXT NOT NULL DEFAULT 'completed'",
        )
        await _ensure_column(
            db,
            "provider_requests",
            "outcome_unknown",
            "INTEGER NOT NULL DEFAULT 0",
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_provider_requests_task "
            "ON provider_requests(task_id, created_at)"
        )
        await db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_provider_requests_request_id "
            "ON provider_requests(provider, request_id) WHERE request_id IS NOT NULL"
        )
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
                proxy_id      INTEGER,
                status        TEXT NOT NULL DEFAULT 'active',
                captcha_count INTEGER DEFAULT 0,
                last_checked  TEXT,
                created_at    TEXT NOT NULL
            )
        """)
        await _ensure_column(db, "accounts", "proxy_id", "INTEGER")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_accounts_proxy_id ON accounts(proxy_id)")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS proxy_profiles (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT NOT NULL UNIQUE,
                proxy_type   TEXT NOT NULL DEFAULT 'http',
                server       TEXT NOT NULL,
                username     TEXT,
                password     TEXT,
                status       TEXT NOT NULL DEFAULT 'active',
                last_checked TEXT,
                last_error   TEXT,
                created_at   TEXT NOT NULL,
                updated_at   TEXT NOT NULL
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_proxy_profiles_status ON proxy_profiles(status)")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS candidate_accounts (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                source        TEXT,
                phone         TEXT,
                sms_link      TEXT,
                fm_link       TEXT,
                user_id       TEXT,
                nickname      TEXT,
                password      TEXT,
                registered_at TEXT,
                cookie_json   TEXT,
                note          TEXT,
                created_at    TEXT NOT NULL,
                updated_at    TEXT NOT NULL
            )
        """)
        await _ensure_column(db, "candidate_accounts", "note", "TEXT")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_candidate_accounts_phone ON candidate_accounts(phone)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_candidate_accounts_user_id ON candidate_accounts(user_id)")
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


def _candidate_cookie_summary(cookie_json: str) -> Dict:
    names = []
    if cookie_json:
        try:
            decoded = json.loads(cookie_json)
            if isinstance(decoded, list):
                names = [str(item.get("name", "")) for item in decoded if isinstance(item, dict)]
        except json.JSONDecodeError:
            names = []
    return {
        "cookie_count": len(names),
        "has_web_session": "web_session" in names,
        "has_a1": "a1" in names,
        "has_web_id": "webId" in names,
        "has_gid": "gid" in names,
        "has_xsecappid": "xsecappid" in names,
        "has_id_token": "id_token" in names,
        "has_customer_sso": "customer-sso-sid" in names,
    }


def _decode_candidate_row(row) -> Dict:
    item = dict(row)
    item.update(_candidate_cookie_summary(item.get("cookie_json") or ""))
    return item


async def list_candidate_accounts() -> List[Dict]:
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM candidate_accounts ORDER BY updated_at DESC, id DESC"
        )
        rows = await cursor.fetchall()
    return [_decode_candidate_row(r) for r in rows]


async def upsert_candidate_account(item: Dict) -> int:
    now = _now()
    phone = (item.get("phone") or "").strip()
    user_id = (item.get("user_id") or "").strip()
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = None
        if phone:
            cur = await db.execute("SELECT id FROM candidate_accounts WHERE phone=? LIMIT 1", (phone,))
            row = await cur.fetchone()
        if not row and user_id:
            cur = await db.execute("SELECT id FROM candidate_accounts WHERE user_id=? LIMIT 1", (user_id,))
            row = await cur.fetchone()
        values = (
            item.get("source", ""),
            phone,
            item.get("sms_link", ""),
            item.get("fm_link", ""),
            user_id,
            item.get("nickname", ""),
            item.get("password", ""),
            item.get("registered_at", ""),
            item.get("cookie_json", ""),
            item.get("note", ""),
            now,
        )
        if row:
            await db.execute(
                "UPDATE candidate_accounts SET source=?, phone=?, sms_link=?, fm_link=?, user_id=?, "
                "nickname=?, password=?, registered_at=?, cookie_json=?, note=?, updated_at=? WHERE id=?",
                (*values, row["id"]),
            )
            candidate_id = row["id"]
        else:
            cur = await db.execute(
                "INSERT INTO candidate_accounts "
                "(source, phone, sms_link, fm_link, user_id, nickname, password, registered_at, "
                "cookie_json, note, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (*values[:-1], now, now),
            )
            candidate_id = cur.lastrowid
        await db.commit()
        return candidate_id


async def delete_candidate_account(candidate_id: int):
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        await db.execute("DELETE FROM candidate_accounts WHERE id=?", (candidate_id,))
        await db.commit()


async def create_task(
    task_type: TaskType | str,
    params: Dict,
    provider: TaskProvider | str = TaskProvider.LOCAL,
    dedupe: bool = True,
) -> int:
    task_type_value = _task_type_value(task_type)
    provider_value = _task_provider_value(provider)
    if provider_value not in {item.value for item in TaskProvider}:
        raise ValueError(f"Unknown task provider: {provider_value}")
    task_key = task_dedupe_key(task_type_value, params, provider_value)
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        await db.execute("BEGIN IMMEDIATE")
        if dedupe:
            cursor = await db.execute(
                "SELECT id FROM tasks WHERE provider=? AND task_type=? AND task_key=? "
                "AND status IN (?, ?, ?) "
                "AND NOT (status=? AND manual_resume_required=1) "
                "ORDER BY created_at ASC LIMIT 1",
                (
                    provider_value,
                    task_type_value,
                    task_key,
                    *ACTIVE_TASK_STATUSES,
                    TaskStatus.PAUSED.value,
                ),
            )
            row = await cursor.fetchone()
            if row:
                await db.commit()
                return row[0]
        cursor = await db.execute(
            "INSERT INTO tasks (task_type, provider, params, status, created_at, task_key) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                task_type_value,
                provider_value,
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
    expected_lease_owner: str,
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
        values.extend([task_id, expected_lease_owner])
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
            "lease_owner=?, heartbeat_at=?, lease_expires_at=?, retry_at=NULL, "
            "attempt_count=COALESCE(attempt_count, 0) + 1 WHERE id=? AND "
            "(status=? OR (status=? AND (lease_expires_at IS NULL OR lease_expires_at < ?)) "
            "OR (status=? AND manual_resume_required=0 "
            "AND (lease_expires_at IS NULL OR lease_expires_at < ?) "
            "AND (retry_at IS NULL OR retry_at <= ?)))",
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


async def update_task_checkpoint(
    task_id: int,
    lease_owner: str,
    checkpoint: Dict,
) -> bool:
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE tasks SET checkpoint_json=?, heartbeat_at=? "
            "WHERE id=? AND lease_owner=?",
            (json.dumps(checkpoint, ensure_ascii=False), _now(), task_id, lease_owner),
        )
        await db.commit()
        return cursor.rowcount == 1


async def record_provider_request(
    *,
    task_id: int,
    provider: TaskProvider | str,
    endpoint: str,
    request_id: Optional[str] = None,
    http_status: Optional[int] = None,
    business_code: Optional[int] = None,
    duration_ms: Optional[int] = None,
    attempt: int = 1,
    billed: bool = False,
    error_type: Optional[str] = None,
    request_state: str = "completed",
    outcome_unknown: bool = False,
) -> int:
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        cursor = await db.execute(
            "INSERT OR IGNORE INTO provider_requests "
            "(task_id, provider, endpoint, request_id, http_status, business_code, "
            "duration_ms, attempt, billed, error_type, request_state, outcome_unknown, "
            "created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                task_id,
                _task_provider_value(provider),
                endpoint,
                request_id,
                http_status,
                business_code,
                duration_ms,
                attempt,
                1 if billed else 0,
                error_type,
                request_state,
                1 if outcome_unknown else 0,
                _now(),
            ),
        )
        await db.commit()
        return cursor.lastrowid or 0


async def complete_provider_request(
    request_row_id: int,
    *,
    request_id: Optional[str] = None,
    http_status: Optional[int] = None,
    business_code: Optional[int] = None,
    duration_ms: Optional[int] = None,
    attempt: int = 1,
    billed: bool = False,
    error_type: Optional[str] = None,
    outcome_unknown: bool = False,
) -> bool:
    request_state = "unknown" if outcome_unknown else "completed"
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE provider_requests SET request_id=?, http_status=?, business_code=?, "
            "duration_ms=?, attempt=?, billed=?, error_type=?, request_state=?, "
            "outcome_unknown=? WHERE id=?",
            (
                request_id,
                http_status,
                business_code,
                duration_ms,
                attempt,
                1 if billed else 0,
                error_type,
                request_state,
                1 if outcome_unknown else 0,
                request_row_id,
            ),
        )
        await db.commit()
        return cursor.rowcount == 1


async def list_provider_requests(task_id: int, limit: int = 200) -> List[Dict]:
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM provider_requests WHERE task_id=? "
            "ORDER BY created_at ASC LIMIT ?",
            (task_id, limit),
        )
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def fail_expired_tasks_with_inflight_provider_requests() -> List[int]:
    """Stop automatic replay when a sent provider request has no known outcome."""
    now = _now()
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        cursor = await db.execute(
            "SELECT DISTINCT t.id FROM tasks t "
            "JOIN provider_requests r ON r.task_id=t.id "
            "WHERE r.request_state='inflight' AND t.status IN (?, ?, ?) "
            "AND (t.lease_expires_at IS NULL OR t.lease_expires_at < ?)",
            (*ACTIVE_TASK_STATUSES, now),
        )
        task_ids = [row["id"] for row in await cursor.fetchall()]
        if task_ids:
            placeholders = ",".join("?" for _ in task_ids)
            await db.execute(
                f"UPDATE provider_requests SET request_state='unknown', "
                f"outcome_unknown=1, error_type=COALESCE(error_type, 'ProcessInterrupted') "
                f"WHERE request_state='inflight' AND task_id IN ({placeholders})",
                task_ids,
            )
            message = (
                "provider request outcome is unknown after process interruption; "
                "manual confirmation is required before retry"
            )
            await db.execute(
                f"UPDATE tasks SET status=?, completed_at=?, error=?, progress=?, "
                f"progress_data=?, lease_owner=NULL, heartbeat_at=NULL, "
                f"lease_expires_at=NULL WHERE id IN ({placeholders})",
                (
                    TaskStatus.FAILED.value,
                    now,
                    message,
                    message,
                    _encode_progress_data(stage="unknown_outcome", message=message),
                    *task_ids,
                ),
            )
        await db.commit()
    return task_ids


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


async def reset_task_for_resume(
    task_id: int,
    new_params: Dict,
    *,
    clear_checkpoint: bool = False,
):
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        cursor = await db.execute(
            "SELECT task_type, provider FROM tasks WHERE id=?",
            (task_id,),
        )
        row = await cursor.fetchone()
        task_type = row[0] if row else TaskType.SEARCH.value
        provider = row[1] if row else TaskProvider.LOCAL.value
        # Keep existing notes_count/comments_count so history is visible while pending.
        checkpoint_assignment = ", checkpoint_json=NULL" if clear_checkpoint else ""
        await db.execute(
            "UPDATE tasks SET status=?, params=?, task_key=?, started_at=NULL, completed_at=NULL, "
            "error=NULL, progress='resume queued', progress_data=?, retry_at=NULL, "
            "attempt_count=0, result_data=NULL, lease_owner=NULL, heartbeat_at=NULL, lease_expires_at=NULL "
            f", manual_resume_required=0{checkpoint_assignment} WHERE id=?",
            (
                TaskStatus.PENDING.value,
                json.dumps(new_params, ensure_ascii=False),
                task_dedupe_key(task_type, new_params, provider),
                _encode_progress_data(stage="pending", message="resume queued"),
                task_id,
            ),
        )
        await db.commit()


async def requeue_unfinished_tasks(
    provider: TaskProvider | str | None = None,
) -> List[int]:
    now = _now()
    provider_value = _task_provider_value(provider) if provider is not None else None
    provider_clause = " AND provider=?" if provider_value is not None else ""
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "UPDATE tasks SET status=?, started_at=NULL, progress='requeued', progress_data=?, "
            "lease_owner=NULL, heartbeat_at=NULL, lease_expires_at=NULL "
            "WHERE ((status=? AND (lease_expires_at IS NULL OR lease_expires_at<?)) "
            "OR (status=? AND manual_resume_required=0 "
            "AND (retry_at IS NULL OR retry_at<=?)))"
            f"{provider_clause}",
            (
                TaskStatus.PENDING.value,
                _encode_progress_data(stage="pending", message="requeued"),
                TaskStatus.RUNNING.value,
                now,
                TaskStatus.PAUSED.value,
                now,
                *([provider_value] if provider_value is not None else []),
            ),
        )
        await db.commit()
        cursor = await db.execute(
            f"SELECT id FROM tasks WHERE status=?{provider_clause} ORDER BY created_at ASC",
            (
                TaskStatus.PENDING.value,
                *([provider_value] if provider_value is not None else []),
            ),
        )
        rows = await cursor.fetchall()
    return [r["id"] for r in rows]


async def pause_unfinished_tasks(
    progress: str = "waiting for account pool recovery",
    provider: TaskProvider | str | None = None,
) -> List[int]:
    progress_data = _encode_progress_data(stage="paused", message=progress)
    now = _now()
    provider_value = _task_provider_value(provider) if provider is not None else None
    provider_clause = " AND provider=?" if provider_value is not None else ""
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(
            "UPDATE tasks SET status=?, progress=?, progress_data=?, "
            "lease_owner=NULL, heartbeat_at=NULL, lease_expires_at=NULL "
            "WHERE (status IN (?, ?) OR "
            "(status=? AND (lease_expires_at IS NULL OR lease_expires_at<?)))"
            f"{provider_clause}",
            (
                TaskStatus.PAUSED.value,
                progress,
                progress_data,
                TaskStatus.PENDING.value,
                TaskStatus.PAUSED.value,
                TaskStatus.RUNNING.value,
                now,
                *([provider_value] if provider_value is not None else []),
            ),
        )
        await db.commit()
        cursor = await db.execute(
            f"SELECT id FROM tasks WHERE status=?{provider_clause} ORDER BY created_at ASC",
            (
                TaskStatus.PAUSED.value,
                *([provider_value] if provider_value is not None else []),
            ),
        )
        rows = await cursor.fetchall()
    return [r["id"] for r in rows]


async def list_paused_task_ids(
    limit: int = 100,
    provider: TaskProvider | str | None = None,
) -> List[int]:
    provider_value = _task_provider_value(provider) if provider is not None else None
    provider_clause = " AND provider=?" if provider_value is not None else ""
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id FROM tasks WHERE status=? AND lease_owner IS NULL "
            "AND manual_resume_required=0 "
            "AND (retry_at IS NULL OR retry_at<=?)"
            f"{provider_clause} ORDER BY created_at ASC LIMIT ?",
            (
                TaskStatus.PAUSED.value,
                _now(),
                *([provider_value] if provider_value is not None else []),
                limit,
            ),
        )
        rows = await cursor.fetchall()
    return [r["id"] for r in rows]


async def list_expired_running_task_ids(
    limit: int = 100,
    provider: TaskProvider | str | None = None,
) -> List[int]:
    now = _now()
    provider_value = _task_provider_value(provider) if provider is not None else None
    provider_clause = " AND provider=?" if provider_value is not None else ""
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id FROM tasks WHERE status=? AND "
            "(lease_expires_at IS NULL OR lease_expires_at < ?) "
            f"{provider_clause} ORDER BY created_at ASC LIMIT ?",
            (
                TaskStatus.RUNNING.value,
                now,
                *([provider_value] if provider_value is not None else []),
                limit,
            ),
        )
        rows = await cursor.fetchall()
    return [r["id"] for r in rows]


async def pause_expired_running_tasks(
    progress: str = "waiting for account pool recovery",
    provider: TaskProvider | str | None = None,
) -> List[int]:
    now = _now()
    provider_value = _task_provider_value(provider) if provider is not None else None
    provider_clause = " AND provider=?" if provider_value is not None else ""
    progress_data = _encode_progress_data(stage="paused", message=progress, updated_at=now)
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        cursor = await db.execute(
            "SELECT id FROM tasks WHERE status=? AND "
            "(lease_expires_at IS NULL OR lease_expires_at < ?) "
            f"{provider_clause} ORDER BY created_at ASC",
            (
                TaskStatus.RUNNING.value,
                now,
                *([provider_value] if provider_value is not None else []),
            ),
        )
        rows = await cursor.fetchall()
        ids = [r["id"] for r in rows]
        if ids:
            placeholders = ",".join("?" for _ in ids)
            await db.execute(
                f"UPDATE tasks SET status=?, progress=?, progress_data=?, "
                "lease_owner=NULL, heartbeat_at=NULL, lease_expires_at=NULL "
                f"WHERE id IN ({placeholders}) AND status=? AND "
                "(lease_expires_at IS NULL OR lease_expires_at < ?)",
                (
                    TaskStatus.PAUSED.value,
                    progress,
                    progress_data,
                    *ids,
                    TaskStatus.RUNNING.value,
                    now,
                ),
            )
        await db.commit()
    return ids


async def find_latest_search_task(
    keyword: str,
    provider: TaskProvider | str = TaskProvider.LOCAL,
    scope_params: Optional[Dict] = None,
) -> Optional[Dict]:
    provider_value = _task_provider_value(provider)
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM tasks WHERE provider=? AND task_type=? "
            "AND json_extract(params,'$.keyword')=? ORDER BY created_at DESC LIMIT 100",
            (provider_value, TaskType.SEARCH.value, keyword),
        )
        rows = await cursor.fetchall()
    expected_scope = (
        task_scope_key(TaskType.SEARCH, scope_params, provider_value)
        if scope_params is not None
        else None
    )
    for row in rows:
        task = _decode_task_row(row)
        if expected_scope is None:
            return task
        if task_scope_key(TaskType.SEARCH, _task_params(task), provider_value) == expected_scope:
            return task
    return None


async def find_latest_creator_task(
    creator_input: str,
    provider: TaskProvider | str = TaskProvider.LOCAL,
    scope_params: Optional[Dict] = None,
) -> Optional[Dict]:
    provider_value = _task_provider_value(provider)
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM tasks WHERE provider=? AND task_type=? "
            "AND json_extract(params,'$.creator_input')=? ORDER BY created_at DESC LIMIT 100",
            (provider_value, TaskType.CREATOR.value, creator_input),
        )
        rows = await cursor.fetchall()
    expected_scope = (
        task_scope_key(TaskType.CREATOR, scope_params, provider_value)
        if scope_params is not None
        else None
    )
    for row in rows:
        task = _decode_task_row(row)
        if expected_scope is None:
            return task
        if task_scope_key(TaskType.CREATOR, _task_params(task), provider_value) == expected_scope:
            return task
    return None


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
        cursor = await db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='xhs_content_source'"
        )
        has_source_attribution = await cursor.fetchone() is not None
        for task in tasks:
            provider = task.get("provider") or TaskProvider.LOCAL.value
            if provider != TaskProvider.LOCAL.value and has_source_attribution:
                cursor = await db.execute(
                    "SELECT entity_type, COUNT(DISTINCT entity_id) "
                    "FROM xhs_content_source WHERE provider=? AND task_id=? "
                    "AND entity_type IN ('note', 'comment') GROUP BY entity_type",
                    (provider, task["id"]),
                )
                attributed_counts = dict(await cursor.fetchall())
                notes_count = attributed_counts.get("note", 0)
                comments_count = attributed_counts.get("comment", 0)
                task["notes_count"] = notes_count
                task["comments_count"] = comments_count
                progress_data = task.get("progress_data")
                if isinstance(progress_data, dict):
                    progress_data["notes_count"] = notes_count
                    progress_data["comments_count"] = comments_count
                continue

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


async def list_proxy_profiles(include_secret: bool = False) -> List[Dict]:
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM proxy_profiles ORDER BY id")
        rows = await cursor.fetchall()
    profiles = [dict(r) for r in rows]
    if not include_secret:
        for profile in profiles:
            if profile.get("password"):
                profile["password"] = ""
                profile["has_password"] = True
            else:
                profile["has_password"] = False
    return profiles


async def get_proxy_profile(proxy_id: Optional[int], include_secret: bool = True) -> Optional[Dict]:
    if not proxy_id:
        return None
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM proxy_profiles WHERE id=?", (proxy_id,))
        row = await cursor.fetchone()
    if not row:
        return None
    profile = dict(row)
    if not include_secret and profile.get("password"):
        profile["password"] = ""
        profile["has_password"] = True
    elif not include_secret:
        profile["has_password"] = False
    return profile


async def add_proxy_profile(item: Dict) -> int:
    now = _now()
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        try:
            cursor = await db.execute(
                "INSERT INTO proxy_profiles "
                "(name, proxy_type, server, username, password, status, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    item.get("name", "").strip(),
                    item.get("proxy_type", "http"),
                    item.get("server", "").strip(),
                    item.get("username", "").strip(),
                    item.get("password", ""),
                    item.get("status", "active"),
                    now,
                    now,
                ),
            )
        except aiosqlite.IntegrityError as exc:
            raise ValueError("Proxy profile name already exists.") from exc
        await db.commit()
        return cursor.lastrowid


async def update_proxy_profile(proxy_id: int, **kwargs):
    if not kwargs:
        return
    allowed = {"name", "proxy_type", "server", "username", "password", "status", "last_checked", "last_error"}
    unknown = set(kwargs) - allowed
    if unknown:
        raise ValueError(f"Unknown proxy fields: {sorted(unknown)}")
    kwargs["updated_at"] = _now()
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        fields = [f"{k}=?" for k in kwargs]
        values = list(kwargs.values()) + [proxy_id]
        try:
            await db.execute(f"UPDATE proxy_profiles SET {', '.join(fields)} WHERE id=?", values)
        except aiosqlite.IntegrityError as exc:
            raise ValueError("Proxy profile name already exists.") from exc
        await db.commit()


async def delete_proxy_profile(proxy_id: int):
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM accounts WHERE proxy_id=?", (proxy_id,))
        row = await cursor.fetchone()
        if row and row[0] > 0:
            raise ValueError("Proxy profile is still bound to accounts.")
        await db.execute("DELETE FROM proxy_profiles WHERE id=?", (proxy_id,))
        await db.commit()


async def add_account(name: str, cookie: str, proxy_id: Optional[int] = None) -> int:
    async with aiosqlite.connect(SERVICE_DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO accounts (name, cookie, proxy_id, status, created_at) VALUES (?,?,?,?,?)",
            (name, cookie, proxy_id, AccountStatus.ACTIVE.value, _now()),
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
