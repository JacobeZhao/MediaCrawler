# -*- coding: utf-8 -*-
"""
Async task queue: processes XHS crawl jobs one at a time.
"""
import asyncio
import json
import socket
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from config.settings import settings
from . import service_db as db
from .circuit_breaker import circuit_breaker
from .crawler_engine import CaptchaException, _is_recoverable_account_error

if TYPE_CHECKING:
    from .account_pool import AccountPool

_LEASE_SECONDS = 300
_PAUSED_REQUEUE_INTERVAL = 30


def _progress_data(
    stage: str,
    message: str,
    notes_count: Optional[int] = None,
    comments_count: Optional[int] = None,
) -> str:
    return json.dumps(
        {
            "stage": stage,
            "message": message,
            "notes_count": notes_count,
            "comments_count": comments_count,
            "updated_at": datetime.now().isoformat(),
        },
        ensure_ascii=False,
    )


class TaskManager:
    def __init__(self, pool: "AccountPool"):
        self._pool = pool
        self._queue: asyncio.Queue = asyncio.Queue()
        self._queued_task_ids: set[int] = set()
        self._worker_task: Optional[asyncio.Task] = None
        self._paused_requeue_task: Optional[asyncio.Task] = None
        self._lease_owner = f"{socket.gethostname()}:{uuid.uuid4().hex}"
        self._current_task_id: Optional[int] = None

    async def start(self):
        if self._pool.has_ready_engine():
            await self._requeue_unfinished()
        else:
            await db.pause_unfinished_tasks()
        self._worker_task = asyncio.create_task(self._worker(), name="task-worker")
        self._paused_requeue_task = asyncio.create_task(
            self._paused_requeue_loop(), name="paused-task-requeue"
        )

    async def stop(self):
        if self._paused_requeue_task:
            self._paused_requeue_task.cancel()
            try:
                await self._paused_requeue_task
            except asyncio.CancelledError:
                pass
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        if self._current_task_id is not None:
            await db.update_task_status_if_owned(
                self._current_task_id,
                self._lease_owner,
                db.TaskStatus.PAUSED,
                progress="paused during service shutdown",
                lease_owner=None,
                lease_expires_at=None,
            )
            self._current_task_id = None

    async def submit(self, task_type: str, params: dict) -> int:
        if self.queue_size() >= settings.max_queue_size:
            raise ValueError(f"Task queue is full ({settings.max_queue_size}).")
        task_id = await db.create_task(task_type, params)
        await self._enqueue(task_id)
        return task_id

    def queue_size(self) -> int:
        return self._queue.qsize()

    async def requeue(self, task_id: int):
        """Re-queue an existing task without creating a new record."""
        await self._enqueue(task_id)

    async def requeue_paused_tasks_now(self) -> int:
        """Wake paused/expired tasks immediately after account recovery."""
        if not self._pool.has_ready_engine():
            return 0
        task_ids = await db.list_expired_running_task_ids()
        task_ids.extend(await db.list_paused_task_ids())
        unique_task_ids = list(dict.fromkeys(task_ids))
        for task_id in unique_task_ids:
            await self._enqueue(task_id)
        return len(unique_task_ids)

    async def _enqueue(self, task_id: int):
        if task_id in self._queued_task_ids:
            return
        self._queued_task_ids.add(task_id)
        await self._queue.put(task_id)

    async def _requeue_unfinished(self):
        """On startup, re-queue any tasks that were pending, running, or paused."""
        for task_id in await db.requeue_unfinished_tasks():
            await self._enqueue(task_id)

    async def _paused_requeue_loop(self):
        while True:
            try:
                await asyncio.sleep(_PAUSED_REQUEUE_INTERVAL)
                if not self._pool.has_ready_engine():
                    await db.pause_expired_running_tasks()
                    continue
                for task_id in await db.list_expired_running_task_ids():
                    await self._enqueue(task_id)
                for task_id in await db.list_paused_task_ids():
                    await self._enqueue(task_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                import traceback
                traceback.print_exc()

    async def _worker(self):
        while True:
            task_id = await self._queue.get()
            try:
                await self._run(task_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                import traceback
                traceback.print_exc()
            finally:
                self._queued_task_ids.discard(task_id)
                self._queue.task_done()

    async def _run(self, task_id: int):
        if circuit_breaker.is_open():
            await db.update_task_status(
                task_id,
                db.TaskStatus.PAUSED,
                progress="paused by risk circuit breaker",
                progress_data=_progress_data(
                    "paused",
                    f"risk circuit breaker open until {circuit_breaker.open_until.isoformat()}",
                ),
                lease_owner=None,
                heartbeat_at=None,
                lease_expires_at=None,
            )
            return

        claimed = await db.claim_task(task_id, self._lease_owner, lease_seconds=_LEASE_SECONDS)
        if not claimed:
            return

        task = await db.get_task(task_id)
        if not task:
            await db.release_task_lease(task_id, self._lease_owner)
            return

        self._current_task_id = task_id
        params = json.loads(task["params"])

        async def progress_cb(
            msg: str,
            notes_count: Optional[int] = None,
            comments_count: Optional[int] = None,
            stage: Optional[str] = None,
        ):
            await db.heartbeat_task(
                task_id,
                self._lease_owner,
                lease_seconds=_LEASE_SECONDS,
                progress=msg,
                notes_count=notes_count,
                comments_count=comments_count,
                stage=stage or "running",
                message=msg,
            )

        max_retries = min(
            max(self._pool.pool_size() + 1, 3),
            max(1, settings.task_max_account_switches + 1),
        )
        tried_engines: set = set()
        run_started_at = datetime.now()

        for attempt in range(max_retries):
            if (datetime.now() - run_started_at).total_seconds() > settings.task_max_runtime_sec:
                await db.update_task_status_if_owned(
                    task_id,
                    self._lease_owner,
                    db.TaskStatus.PAUSED,
                    error="task runtime budget exceeded",
                    progress="paused after reaching runtime budget",
                    progress_data=_progress_data("paused", "paused after reaching runtime budget"),
                    lease_owner=None,
                    heartbeat_at=None,
                    lease_expires_at=None,
                )
                self._current_task_id = None
                return

            if circuit_breaker.is_open():
                await db.update_task_status_if_owned(
                    task_id,
                    self._lease_owner,
                    db.TaskStatus.PAUSED,
                    progress="paused by risk circuit breaker",
                    progress_data=_progress_data(
                        "paused",
                        f"risk circuit breaker open until {circuit_breaker.open_until.isoformat()}",
                    ),
                    lease_owner=None,
                    heartbeat_at=None,
                    lease_expires_at=None,
                )
                self._current_task_id = None
                return

            eng = await self._pool.get_healthy_engine()

            if eng is None:
                updated = await db.update_task_status_if_owned(
                    task_id,
                    self._lease_owner,
                    db.TaskStatus.PAUSED,
                    progress="waiting for account pool recovery",
                    progress_data=_progress_data("paused", "waiting for account pool recovery"),
                    lease_owner=None,
                    heartbeat_at=None,
                    lease_expires_at=None,
                )
                self._current_task_id = None
                return

            eng_key = id(eng)
            if eng_key in tried_engines:
                await db.update_task_status_if_owned(
                    task_id,
                    self._lease_owner,
                    db.TaskStatus.PAUSED,
                    error="all available accounts need recovery",
                    progress="waiting for account pool recovery",
                    progress_data=_progress_data("paused", "waiting for account pool recovery"),
                    lease_owner=None,
                    heartbeat_at=None,
                    lease_expires_at=None,
                )
                self._current_task_id = None
                return
            tried_engines.add(eng_key)

            try:
                if task["task_type"] == db.TaskType.SEARCH.value:
                    result = await eng.search_keyword(
                        keyword=params["keyword"],
                        max_notes=params.get("max_notes", 20),
                        enable_comments=True,
                        enable_images=False,
                        max_comments=params.get("max_comments", 20),
                        progress_cb=progress_cb,
                        force=params.get("force", False),
                        sort_type=params.get("sort_type", "popularity_descending"),
                        days_limit=params.get("days_limit", 0),
                    )
                elif task["task_type"] == db.TaskType.CREATOR.value:
                    result = await eng.crawl_creator(
                        creator_input=params["creator_input"],
                        max_notes=params.get("max_notes", 20),
                        enable_images=True,
                        enable_comments=False,
                        max_comments=0,
                        progress_cb=progress_cb,
                        force=params.get("force", False),
                    )
                elif task["task_type"] == db.TaskType.NOTE.value:
                    note_items = params.get("notes", [])
                    result = await eng.crawl_notes(
                        note_items=note_items,
                        progress_cb=progress_cb,
                    )
                    for item in note_items:
                        note_input = item.get("note_input", "").strip()
                        if not note_input:
                            continue
                        if note_input.startswith("http"):
                            from media_platform.xhs.help import parse_note_info_from_note_url
                            note_id = parse_note_info_from_note_url(note_input).note_id
                        else:
                            note_id = note_input
                        await db.upsert_note_tag(
                            note_id,
                            item.get("d_level", ""),
                            item.get("quality", ""),
                        )
                else:
                    raise ValueError(f"Unknown task type: {task['task_type']}")

                total_notes = result.get("total_notes_in_db", result.get("notes_count", 0))
                total_comments = result.get("total_comments_in_db", result.get("comments_count", 0))
                await db.update_task_status_if_owned(
                    task_id,
                    self._lease_owner,
                    db.TaskStatus.COMPLETED,
                    completed_at=datetime.now().isoformat(),
                    notes_count=total_notes,
                    comments_count=total_comments,
                    progress="completed",
                    progress_data=_progress_data(
                        "completed",
                        "completed",
                        total_notes,
                        total_comments,
                    ),
                    lease_owner=None,
                    lease_expires_at=None,
                )
                self._current_task_id = None
                return

            except Exception as exc:
                if isinstance(exc, CaptchaException) or _is_recoverable_account_error(exc):
                    if isinstance(exc, CaptchaException):
                        await self._pool.mark_captcha(eng)
                        event_type = "captcha"
                    else:
                        await self._pool.mark_temporarily_unavailable(eng)
                        event_type = "account_error"
                    await circuit_breaker.record_risk_event(
                        event_type,
                        account_id=eng.account_id,
                        task_id=task_id,
                        message=str(exc),
                    )
                    if settings.task_pause_on_account_error:
                        await db.update_task_status_if_owned(
                            task_id,
                            self._lease_owner,
                            db.TaskStatus.PAUSED,
                            error=f"account protection pause: {type(exc).__name__}",
                            progress="paused for account protection",
                            progress_data=_progress_data(
                                "paused",
                                f"paused for account protection: {type(exc).__name__}",
                            ),
                            lease_owner=None,
                            heartbeat_at=None,
                            lease_expires_at=None,
                        )
                        self._current_task_id = None
                        return
                    heartbeat_ok = await db.heartbeat_task(
                        task_id,
                        self._lease_owner,
                        lease_seconds=_LEASE_SECONDS,
                        progress=f"account error {type(exc).__name__}; switching account ({attempt + 1})",
                        stage="account_switch",
                        message=f"account error {type(exc).__name__}; switching account ({attempt + 1})",
                    )
                    if not heartbeat_ok:
                        self._current_task_id = None
                        return
                    continue

                await db.update_task_status_if_owned(
                    task_id,
                    self._lease_owner,
                    db.TaskStatus.FAILED,
                    completed_at=datetime.now().isoformat(),
                    error=str(exc),
                    progress=f"failed: {exc}",
                    progress_data=_progress_data("failed", f"failed: {exc}"),
                    lease_owner=None,
                    lease_expires_at=None,
                )
                self._current_task_id = None
                return

        await db.update_task_status_if_owned(
            task_id,
            self._lease_owner,
            db.TaskStatus.PAUSED,
            error="exceeded account retry limit; waiting for recovery",
            progress="waiting for account pool recovery",
            progress_data=_progress_data("paused", "waiting for account pool recovery"),
            lease_owner=None,
            heartbeat_at=None,
            lease_expires_at=None,
        )
        self._current_task_id = None
