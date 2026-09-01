# -*- coding: utf-8 -*-
"""Provider-aware asynchronous task scheduling and lease management."""
from __future__ import annotations

import asyncio
import json
import socket
import traceback
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from config.settings import settings
from tools.redaction import redact_sensitive_text

from . import service_db as db
from .executors.base import (
    ExecutionContext,
    ExecutorLeaseLost,
    ExecutorPaused,
    ProviderReadiness,
    TaskExecutor,
)
from .executors.registry import ExecutorRegistry


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
    def __init__(self, registry: ExecutorRegistry):
        self._registry = registry
        self._queues: Dict[str, asyncio.Queue[int]] = {
            provider: asyncio.Queue() for provider in self._registry.providers
        }
        self._queued_task_ids: set[int] = set()
        self._deferred_requeues: set[int] = set()
        self._enqueue_lock = asyncio.Lock()
        self._worker_tasks: Dict[str, asyncio.Task] = {}
        self._paused_requeue_task: Optional[asyncio.Task] = None
        self._lease_owner = f"{socket.gethostname()}:{uuid.uuid4().hex}"
        self._current_task_ids: Dict[str, int] = {}

    @property
    def providers(self) -> tuple[str, ...]:
        return self._registry.providers

    @property
    def registry(self) -> ExecutorRegistry:
        return self._registry

    def get_executor(self, provider: db.TaskProvider | str) -> TaskExecutor:
        return self._registry.get(self._provider_value(provider))

    async def provider_readiness(
        self,
        provider: db.TaskProvider | str,
    ) -> ProviderReadiness:
        provider_value = self._provider_value(provider)
        executor = self._registry.get(provider_value)
        try:
            return await executor.readiness()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return ProviderReadiness(
                enabled=True,
                ready=False,
                reason="readiness_check_failed",
                details={"error_type": type(exc).__name__},
            )

    async def readiness(self) -> Dict[str, ProviderReadiness]:
        return {
            provider: await self.provider_readiness(provider)
            for provider in self._registry.providers
        }

    async def start(self) -> None:
        if self._paused_requeue_task is not None:
            return

        await self._prepare_unfinished_tasks()
        self._worker_tasks = {
            provider: asyncio.create_task(
                self._worker(provider),
                name=f"task-worker-{provider}",
            )
            for provider in self._registry.providers
        }
        self._paused_requeue_task = asyncio.create_task(
            self._paused_requeue_loop(),
            name="paused-task-requeue",
        )

    async def stop(self) -> None:
        if self._paused_requeue_task is not None:
            self._paused_requeue_task.cancel()
            try:
                await self._paused_requeue_task
            except asyncio.CancelledError:
                pass
            self._paused_requeue_task = None

        current_tasks = dict(self._current_task_ids)
        workers = list(self._worker_tasks.values())
        for worker in workers:
            worker.cancel()
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)

        # The worker normally pauses itself on cancellation. This is a fallback for
        # cancellation that happened between claiming a task and entering execute().
        current_tasks.update(self._current_task_ids)
        for task_id in dict.fromkeys(current_tasks.values()):
            await db.update_task_status_if_owned(
                task_id,
                self._lease_owner,
                db.TaskStatus.PAUSED,
                progress="paused during service shutdown",
                progress_data=_progress_data(
                    "paused",
                    "paused during service shutdown",
                ),
                retry_at=None,
                lease_owner=None,
                heartbeat_at=None,
                lease_expires_at=None,
            )

        self._worker_tasks.clear()
        self._current_task_ids.clear()

    async def submit(
        self,
        task_type: str,
        params: dict,
        provider: db.TaskProvider | str = db.TaskProvider.LOCAL,
    ) -> int:
        provider_value = self._provider_value(provider)
        self._registry.get(provider_value)
        if self.queue_size() >= settings.max_queue_size:
            raise ValueError(f"Task queue is full ({settings.max_queue_size}).")
        task_id = await db.create_task(
            task_type,
            params,
            provider=provider_value,
        )
        await self._enqueue(task_id)
        return task_id

    def queue_size(self, provider: db.TaskProvider | str | None = None) -> int:
        if provider is None:
            return sum(queue.qsize() for queue in self._queues.values())
        provider_value = self._provider_value(provider)
        try:
            queue = self._queues[provider_value]
        except KeyError as exc:
            raise ValueError(f"Unknown task provider: {provider_value}") from exc
        return queue.qsize()

    async def requeue(self, task_id: int) -> None:
        """Requeue an existing task using the provider stored on the task."""
        await self._enqueue(task_id)

    async def requeue_paused_tasks_now(self) -> int:
        """Wake local tasks after local account recovery."""
        provider = db.TaskProvider.LOCAL.value
        if provider not in self._queues:
            return 0
        readiness = await self.provider_readiness(provider)
        if not readiness.ready:
            return 0
        return await self._requeue_provider_tasks_now(provider)

    async def _prepare_unfinished_tasks(self) -> None:
        await db.fail_expired_tasks_with_inflight_provider_requests()
        registered = set(self._registry.providers)
        for provider in self._registry.providers:
            readiness = await self.provider_readiness(provider)
            if readiness.ready:
                task_ids = await db.requeue_unfinished_tasks(provider=provider)
                for task_id in task_ids:
                    await self._enqueue(task_id)
            else:
                await db.pause_unfinished_tasks(
                    progress=self._readiness_message(provider, readiness),
                    provider=provider,
                )

        # Tasks retain their original provider even when that provider is not
        # configured in this process. Keep them paused instead of misrouting them.
        for provider in db.TaskProvider:
            if provider.value not in registered:
                await db.pause_unfinished_tasks(
                    progress=f"task provider unavailable: {provider.value}",
                    provider=provider.value,
                )

    async def _enqueue(self, task_id: int) -> None:
        async with self._enqueue_lock:
            if task_id in self._queued_task_ids:
                task = await db.get_task(task_id)
                if task and task.get("status") == db.TaskStatus.PENDING.value:
                    self._deferred_requeues.add(task_id)
                return

            task = await db.get_task(task_id)
            if not task:
                return
            if task.get("status") not in db.ACTIVE_TASK_STATUSES:
                return
            provider = task.get("provider") or db.TaskProvider.LOCAL.value
            if self._retry_is_deferred(task):
                if task.get("status") != db.TaskStatus.PAUSED.value:
                    message = "waiting for provider retry window"
                    await db.update_task_status(
                        task_id,
                        db.TaskStatus.PAUSED,
                        progress=message,
                        progress_data=_progress_data("paused", message),
                        retry_at=task.get("retry_at"),
                        lease_owner=None,
                        heartbeat_at=None,
                        lease_expires_at=None,
                    )
                return
            try:
                queue = self._queues[provider]
            except KeyError as exc:
                raise ValueError(f"Unknown task provider: {provider}") from exc

            self._queued_task_ids.add(task_id)
            queue.put_nowait(task_id)

    async def _requeue_provider_tasks_now(self, provider: str) -> int:
        task_ids = await db.list_expired_running_task_ids(provider=provider)
        task_ids.extend(await db.list_paused_task_ids(provider=provider))
        unique_task_ids = list(dict.fromkeys(task_ids))
        for task_id in unique_task_ids:
            await self._enqueue(task_id)
        return len(unique_task_ids)

    async def _paused_requeue_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(_PAUSED_REQUEUE_INTERVAL)
                await db.fail_expired_tasks_with_inflight_provider_requests()
                for provider in self._registry.providers:
                    readiness = await self.provider_readiness(provider)
                    if not readiness.ready:
                        await db.pause_expired_running_tasks(
                            progress=self._readiness_message(provider, readiness),
                            provider=provider,
                        )
                        continue
                    await self._requeue_provider_tasks_now(provider)
            except asyncio.CancelledError:
                raise
            except Exception:
                traceback.print_exc()

    async def _worker(self, provider: str) -> None:
        queue = self._queues[provider]
        while True:
            task_id = await queue.get()
            try:
                await self._run(task_id, provider)
            except asyncio.CancelledError:
                raise
            except Exception:
                traceback.print_exc()
            finally:
                async with self._enqueue_lock:
                    self._queued_task_ids.discard(task_id)
                    requeue_deferred = task_id in self._deferred_requeues
                    self._deferred_requeues.discard(task_id)
                queue.task_done()
                if requeue_deferred:
                    await self._enqueue(task_id)

    async def _run(self, task_id: int, worker_provider: str) -> None:
        claimed = await db.claim_task(
            task_id,
            self._lease_owner,
            lease_seconds=_LEASE_SECONDS,
        )
        if not claimed:
            return

        self._current_task_ids[worker_provider] = task_id
        try:
            task = await db.get_task(task_id)
            if not task:
                await db.release_task_lease(task_id, self._lease_owner)
                return

            provider = task.get("provider") or db.TaskProvider.LOCAL.value
            if provider != worker_provider:
                await db.release_task_lease(task_id, self._lease_owner)
                raise RuntimeError(
                    f"Task {task_id} was queued for {worker_provider}, not {provider}."
                )

            readiness = await self.provider_readiness(provider)
            if not readiness.ready:
                await self._pause_owned_task(
                    task_id,
                    self._readiness_message(provider, readiness),
                )
                return

            params = self._decode_params(task.get("params"))

            async def progress_callback(
                *,
                message: str,
                stage: str = "running",
                notes_count: Optional[int] = None,
                comments_count: Optional[int] = None,
                lease_seconds: Optional[int] = None,
            ) -> bool:
                effective_lease = _LEASE_SECONDS
                if lease_seconds is not None:
                    effective_lease = max(1, int(lease_seconds))
                return await db.heartbeat_task(
                    task_id,
                    self._lease_owner,
                    lease_seconds=effective_lease,
                    progress=message,
                    notes_count=notes_count,
                    comments_count=comments_count,
                    stage=stage,
                    message=message,
                )

            async def checkpoint_callback(checkpoint: Dict[str, Any]) -> bool:
                if not isinstance(checkpoint, dict):
                    raise TypeError("Task checkpoint must be a dictionary.")
                updated = await db.update_task_checkpoint(
                    task_id,
                    self._lease_owner,
                    checkpoint,
                )
                if not updated:
                    return False
                return await db.heartbeat_task(
                    task_id,
                    self._lease_owner,
                    lease_seconds=_LEASE_SECONDS,
                )

            context = ExecutionContext(
                task_id=task_id,
                progress_callback=progress_callback,
                checkpoint_callback=checkpoint_callback,
            )
            executor = self._registry.get(provider)

            try:
                result = await executor.execute(task, params, context)
                if not isinstance(result, dict):
                    raise TypeError("Task executor result must be a dictionary.")
            except ExecutorLeaseLost:
                return
            except ExecutorPaused as exc:
                await self._pause_owned_task(
                    task_id,
                    exc.message,
                    error=exc.error,
                    retry_after_seconds=exc.retry_after_seconds,
                )
                return
            except asyncio.CancelledError:
                await asyncio.shield(
                    self._pause_owned_task(
                        task_id,
                        "paused during service shutdown",
                    )
                )
                raise
            except Exception as exc:
                await self._fail_owned_task(task_id, exc)
                return

            notes_count = self._result_count(
                result,
                "total_notes_in_db",
                "notes_count",
            )
            comments_count = self._result_count(
                result,
                "total_comments_in_db",
                "comments_count",
            )
            if result.get("budget_exhausted"):
                message = (
                    "request budget exhausted; submit the task with a higher "
                    "max_requests value to continue"
                )
                await db.update_task_status_if_owned(
                    task_id,
                    self._lease_owner,
                    db.TaskStatus.PAUSED,
                    error=None,
                    notes_count=notes_count,
                    comments_count=comments_count,
                    progress=message,
                    progress_data=_progress_data(
                        "budget_exhausted",
                        message,
                        notes_count,
                        comments_count,
                    ),
                    result_data=json.dumps(result, ensure_ascii=False, default=str),
                    retry_at=None,
                    manual_resume_required=1,
                    lease_owner=None,
                    heartbeat_at=None,
                    lease_expires_at=None,
                )
                return
            await db.update_task_status_if_owned(
                task_id,
                self._lease_owner,
                db.TaskStatus.COMPLETED,
                completed_at=datetime.now().isoformat(),
                error=None,
                notes_count=notes_count,
                comments_count=comments_count,
                progress="completed",
                progress_data=_progress_data(
                    "completed",
                    "completed",
                    notes_count,
                    comments_count,
                ),
                result_data=json.dumps(result, ensure_ascii=False, default=str),
                retry_at=None,
                manual_resume_required=0,
                lease_owner=None,
                lease_expires_at=None,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self._fail_owned_task(task_id, exc)
        finally:
            if self._current_task_ids.get(worker_provider) == task_id:
                self._current_task_ids.pop(worker_provider, None)

    async def _pause_owned_task(
        self,
        task_id: int,
        message: str,
        *,
        error: Optional[str] = None,
        retry_after_seconds: Optional[float] = None,
    ) -> bool:
        message = redact_sensitive_text(message)
        error = redact_sensitive_text(error) if error is not None else None
        retry_at = None
        if retry_after_seconds is not None:
            retry_delay = max(0.0, float(retry_after_seconds))
            retry_at = (datetime.now() + timedelta(seconds=retry_delay)).isoformat()
        return await db.update_task_status_if_owned(
            task_id,
            self._lease_owner,
            db.TaskStatus.PAUSED,
            error=error,
            progress=message,
            progress_data=_progress_data("paused", message),
            retry_at=retry_at,
            manual_resume_required=0,
            lease_owner=None,
            heartbeat_at=None,
            lease_expires_at=None,
        )

    async def _fail_owned_task(self, task_id: int, exc: Exception) -> bool:
        error = redact_sensitive_text(str(exc) or type(exc).__name__)
        return await db.update_task_status_if_owned(
            task_id,
            self._lease_owner,
            db.TaskStatus.FAILED,
            completed_at=datetime.now().isoformat(),
            error=error,
            progress=f"failed: {error}",
            progress_data=_progress_data("failed", f"failed: {error}"),
            retry_at=None,
            manual_resume_required=0,
            lease_owner=None,
            lease_expires_at=None,
        )

    @staticmethod
    def _provider_value(provider: db.TaskProvider | str) -> str:
        if isinstance(provider, db.TaskProvider):
            return provider.value
        return str(provider)

    @staticmethod
    def _decode_params(raw_params: Any) -> Dict[str, Any]:
        if isinstance(raw_params, dict):
            return raw_params
        if isinstance(raw_params, str):
            params = json.loads(raw_params)
            if isinstance(params, dict):
                return params
        raise ValueError("Task params must be a JSON object.")

    @staticmethod
    def _result_count(result: Dict[str, Any], *keys: str) -> int:
        for key in keys:
            if key not in result:
                continue
            try:
                return max(0, int(result[key] or 0))
            except (TypeError, ValueError):
                continue
        return 0

    @staticmethod
    def _retry_is_deferred(task: Dict[str, Any]) -> bool:
        raw_retry_at = task.get("retry_at")
        if not raw_retry_at:
            return False
        try:
            retry_at = datetime.fromisoformat(str(raw_retry_at))
        except (TypeError, ValueError):
            return False
        now = datetime.now(retry_at.tzinfo) if retry_at.tzinfo else datetime.now()
        return retry_at > now

    @staticmethod
    def _readiness_message(provider: str, readiness: ProviderReadiness) -> str:
        if provider == db.TaskProvider.LOCAL.value:
            return "waiting for account pool recovery"
        reason = readiness.reason or ("disabled" if not readiness.enabled else "not ready")
        return f"waiting for {provider} provider readiness: {reason}"
