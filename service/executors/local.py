from __future__ import annotations

import asyncio
import json
import random
from datetime import datetime
from typing import Any, Dict, Set

from config.settings import settings
from media_platform.xhs.help import parse_note_info_from_note_url

from .. import service_db as db
from ..account_pool import AccountPool
from ..circuit_breaker import circuit_breaker
from ..crawler_engine import CaptchaException, _is_recoverable_account_error
from ..rate_limiter import rate_limiter
from .base import (
    ExecutionContext,
    ExecutorLeaseLost,
    ExecutorPaused,
    ProviderReadiness,
    TaskExecutor,
)


class LocalTaskExecutor(TaskExecutor):
    provider = "local"

    def __init__(self, pool: AccountPool, *, enabled: bool = True):
        self._pool = pool
        self._enabled = enabled

    async def readiness(self) -> ProviderReadiness:
        engine = self._pool.get_default_engine()
        runtime_enabled = engine.status != "stopped"
        enabled = self._enabled and runtime_enabled
        ready = enabled and self._pool.has_ready_engine()
        if not self._enabled:
            reason = "disabled"
        elif not runtime_enabled:
            reason = "crawler_engine_stopped"
        elif not ready:
            reason = "no_ready_account"
        else:
            reason = None
        return ProviderReadiness(
            enabled=enabled,
            ready=ready,
            reason=reason,
            details={"ready_accounts": self._pool.ready_count()},
        )

    async def execute(
        self,
        task: Dict[str, Any],
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> Dict[str, Any]:
        if circuit_breaker.is_open():
            retry_after = max(
                0.0,
                (circuit_breaker.open_until - datetime.now()).total_seconds(),
            )
            raise ExecutorPaused(
                "paused by risk circuit breaker",
                retry_after_seconds=retry_after,
            )

        await self._protective_sleep(
            context,
            "startup_jitter",
            "account protection startup delay",
            settings.crawler_task_start_jitter_min_sec,
            settings.crawler_task_start_jitter_max_sec,
        )

        max_retries = min(
            max(self._pool.pool_size() + 1, 3),
            max(1, settings.task_max_account_switches + 1),
        )
        tried_engines: Set[int] = set()
        run_started_at = datetime.now()

        for attempt in range(max_retries):
            if (datetime.now() - run_started_at).total_seconds() > settings.task_max_runtime_sec:
                raise ExecutorPaused(
                    "paused after reaching runtime budget",
                    error="task runtime budget exceeded",
                )

            if circuit_breaker.is_open():
                retry_after = max(
                    0.0,
                    (circuit_breaker.open_until - datetime.now()).total_seconds(),
                )
                raise ExecutorPaused(
                    "paused by risk circuit breaker",
                    retry_after_seconds=retry_after,
                )

            engine = await self._pool.get_healthy_engine()
            if engine is None:
                raise ExecutorPaused("waiting for account pool recovery")

            engine_key = id(engine)
            if engine_key in tried_engines:
                raise ExecutorPaused(
                    "waiting for account pool recovery",
                    error="all available accounts need recovery",
                )
            tried_engines.add(engine_key)

            try:
                return await self._execute_with_engine(
                    engine,
                    task["task_type"],
                    params,
                    context,
                )
            except Exception as exc:
                if not isinstance(exc, CaptchaException) and not _is_recoverable_account_error(exc):
                    raise

                if isinstance(exc, CaptchaException):
                    await self._pool.mark_captcha(engine)
                    event_type = "captcha"
                else:
                    await self._pool.mark_temporarily_unavailable(engine)
                    event_type = "account_error"
                await rate_limiter.penalize(engine.account_id)
                await circuit_breaker.record_risk_event(
                    event_type,
                    account_id=engine.account_id,
                    task_id=context.task_id,
                    message=str(exc),
                )

                if settings.task_pause_on_account_error:
                    raise ExecutorPaused(
                        "paused for account protection",
                        error=f"account protection pause: {type(exc).__name__}",
                    ) from exc

                heartbeat_ok = await context.progress(
                    f"account error {type(exc).__name__}; switching account ({attempt + 1})",
                    stage="account_switch",
                )
                if not heartbeat_ok:
                    raise ExecutorLeaseLost from exc

        raise ExecutorPaused(
            "waiting for account pool recovery",
            error="exceeded account retry limit; waiting for recovery",
        )

    async def _execute_with_engine(
        self,
        engine,
        task_type: str,
        params: Dict[str, Any],
        context: ExecutionContext,
    ) -> Dict[str, Any]:
        async def progress_cb(
            message: str,
            notes_count=None,
            comments_count=None,
            stage=None,
        ):
            ok = await context.progress(
                message,
                stage=stage or "running",
                notes_count=notes_count,
                comments_count=comments_count,
            )
            if not ok:
                raise ExecutorLeaseLost

        if task_type == db.TaskType.SEARCH.value:
            return await engine.search_keyword(
                keyword=params["keyword"],
                max_notes=self._clamp_positive(
                    params.get("max_notes", 20),
                    settings.crawler_task_max_notes_per_task,
                ),
                enable_comments=True,
                enable_images=False,
                max_comments=self._clamp_positive(
                    params.get("max_comments", 20),
                    settings.crawler_task_max_comments_per_note,
                ),
                progress_cb=progress_cb,
                force=params.get("force", False),
                sort_type=params.get("sort_type", "popularity_descending"),
                days_limit=params.get("days_limit", 0),
            )

        if task_type == db.TaskType.CREATOR.value:
            return await engine.crawl_creator(
                creator_input=params["creator_input"],
                max_notes=self._clamp_positive(
                    params.get("max_notes", 20),
                    settings.crawler_task_max_notes_per_task,
                ),
                enable_images=True,
                enable_comments=False,
                max_comments=0,
                progress_cb=progress_cb,
                force=params.get("force", False),
            )

        if task_type == db.TaskType.NOTE.value:
            note_items = params.get("notes", [])
            result = await engine.crawl_notes(
                note_items=note_items,
                progress_cb=progress_cb,
            )
            for item in note_items:
                note_input = item.get("note_input", "").strip()
                if not note_input:
                    continue
                if note_input.startswith("http"):
                    note_id = parse_note_info_from_note_url(note_input).note_id
                else:
                    note_id = note_input
                await db.upsert_note_tag(
                    note_id,
                    item.get("d_level", ""),
                    item.get("quality", ""),
                )
            return result

        raise ValueError(f"Unknown task type: {task_type}")

    @staticmethod
    def _clamp_positive(value: int, limit: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = limit
        if limit <= 0:
            return max(0, parsed)
        return max(0, min(parsed, limit))

    async def _protective_sleep(
        self,
        context: ExecutionContext,
        stage: str,
        message: str,
        min_seconds: float,
        max_seconds: float,
    ) -> None:
        if max_seconds <= 0 or max_seconds < min_seconds:
            return
        seconds = random.uniform(max(0.0, min_seconds), max_seconds)
        if seconds <= 0:
            return
        progress = f"{message}: {int(seconds)}s"
        ok = await context.progress(
            progress,
            stage=stage,
            lease_seconds=300 + int(seconds) + 30,
        )
        if not ok:
            raise ExecutorLeaseLost
        await asyncio.sleep(seconds)
