from __future__ import annotations

import json
from typing import Dict, List

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from config.settings import settings
from ..schemas.tasks import (
    BatchCreatorTaskRequest,
    BatchSearchTaskRequest,
    CreatorTaskRequest,
    JustOneApiOptions,
    NoteTaskRequest,
    SearchTaskRequest,
)

from .. import service_db as sdb
from ..task_manager import TaskManager

TaskStatus = sdb.TaskStatus
TaskType = sdb.TaskType
ACTIVE_EXISTING_STATUSES = {
    TaskStatus.PENDING.value,
    TaskStatus.RUNNING.value,
    TaskStatus.PAUSED.value,
}


class TaskService:
    def __init__(self, task_manager: TaskManager):
        self._task_manager = task_manager

    async def _ensure_provider_ready(self, provider: str):
        try:
            readiness = await self._task_manager.provider_readiness(provider)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        local_can_queue = (
            provider == sdb.TaskProvider.LOCAL.value and readiness.enabled
        )
        if not local_can_queue and (not readiness.enabled or not readiness.ready):
            reason = readiness.reason or "provider_not_ready"
            raise HTTPException(503, f"Task provider {provider} is not ready: {reason}.")

    @staticmethod
    def _request_params(req) -> tuple[str, Dict]:
        provider = req.provider
        params = req.model_dump(exclude={"provider", "provider_options"})
        if provider == sdb.TaskProvider.JUSTONEAPI.value:
            options = req.provider_options or JustOneApiOptions()
            params["provider_options"] = options.model_dump()
        return provider, params

    @staticmethod
    def _budget_exhausted(task: Dict) -> bool:
        result = task.get("result_data")
        return bool(isinstance(result, dict) and result.get("budget_exhausted"))

    async def create_search_task(self, req: SearchTaskRequest):
        provider, params = self._request_params(req)
        await self._ensure_provider_ready(provider)

        if not req.force:
            existing = await sdb.find_latest_search_task(
                req.keyword,
                provider,
                params if provider == sdb.TaskProvider.JUSTONEAPI.value else None,
            )
            if existing:
                if (
                    existing["status"] == TaskStatus.PAUSED.value
                    and self._budget_exhausted(existing)
                ):
                    await sdb.reset_task_for_resume(existing["id"], params)
                    await self._task_manager.requeue(existing["id"])
                    return {
                        "task_id": existing["id"],
                        "provider": provider,
                        "message": "Resumed task with the submitted request budget.",
                    }
                if existing["status"] in ACTIVE_EXISTING_STATUSES:
                    return JSONResponse(
                        status_code=409,
                        content={
                            "conflict": "queued",
                            "existing_task_id": existing["id"],
                            "message": f"Keyword already has a queued task: {existing['id']}",
                        },
                    )
                if existing["status"] == TaskStatus.COMPLETED.value and existing["notes_count"] >= req.max_notes:
                    return JSONResponse(
                        status_code=409,
                        content={
                            "conflict": "completed",
                            "existing_notes": existing["notes_count"],
                            "existing_task_id": existing["id"],
                            "message": f"Keyword already has {existing['notes_count']} notes.",
                        },
                    )
                if existing["status"] == TaskStatus.COMPLETED.value and existing["notes_count"] < req.max_notes:
                    await sdb.reset_task_for_resume(existing["id"], params)
                    await self._task_manager.requeue(existing["id"])
                    return {
                        "task_id": existing["id"],
                        "message": f"Resumed task from {existing['notes_count']} notes to target {req.max_notes}.",
                    }

        task_id = await self._task_manager.submit(TaskType.SEARCH.value, params, provider)
        return {"task_id": task_id, "provider": provider, "message": "Task created."}

    async def create_batch_search_tasks(self, req: BatchSearchTaskRequest):
        provider, common_params = self._request_params(req)
        await self._ensure_provider_ready(provider)
        if len(req.keywords) > settings.max_batch_tasks:
            raise HTTPException(400, f"Batch size exceeds MAX_BATCH_TASKS={settings.max_batch_tasks}.")
        task_ids: List[int] = []
        resumed = 0
        skipped = 0

        for kw in req.keywords:
            kw = kw.strip()
            if not kw:
                continue
            params = {
                "keyword": kw,
                "max_notes": req.max_notes,
                "max_comments": req.max_comments,
                "sort_type": req.sort_type,
                "days_limit": req.days_limit,
            }
            if "provider_options" in common_params:
                params["provider_options"] = common_params["provider_options"]
            existing = await sdb.find_latest_search_task(
                kw,
                provider,
                params if provider == sdb.TaskProvider.JUSTONEAPI.value else None,
            )
            if existing:
                if (
                    existing["status"] == TaskStatus.PAUSED.value
                    and self._budget_exhausted(existing)
                ):
                    await sdb.reset_task_for_resume(existing["id"], params)
                    await self._task_manager.requeue(existing["id"])
                    task_ids.append(existing["id"])
                    resumed += 1
                    continue
                if existing["status"] in ACTIVE_EXISTING_STATUSES:
                    skipped += 1
                    continue
                if existing["status"] == TaskStatus.COMPLETED.value and existing["notes_count"] < req.max_notes:
                    await sdb.reset_task_for_resume(existing["id"], params)
                    await self._task_manager.requeue(existing["id"])
                    task_ids.append(existing["id"])
                    resumed += 1
                    continue
                if existing["status"] == TaskStatus.COMPLETED.value and existing["notes_count"] >= req.max_notes:
                    skipped += 1
                    continue
            task_id = await self._task_manager.submit(TaskType.SEARCH.value, params, provider)
            task_ids.append(task_id)

        return {
            "task_ids": task_ids,
            "count": len(task_ids),
            "resumed": resumed,
            "skipped": skipped,
            "provider": provider,
            "message": f"Created or resumed {len(task_ids)} tasks; skipped {skipped}.",
        }

    async def create_creator_task(self, req: CreatorTaskRequest):
        provider, params = self._request_params(req)
        await self._ensure_provider_ready(provider)

        if not req.force:
            existing = await sdb.find_latest_creator_task(
                req.creator_input,
                provider,
                params if provider == sdb.TaskProvider.JUSTONEAPI.value else None,
            )
            if existing:
                if (
                    existing["status"] == TaskStatus.PAUSED.value
                    and self._budget_exhausted(existing)
                ):
                    await sdb.reset_task_for_resume(existing["id"], params)
                    await self._task_manager.requeue(existing["id"])
                    return {
                        "task_id": existing["id"],
                        "provider": provider,
                        "message": "Resumed task with the submitted request budget.",
                    }
                if existing["status"] in ACTIVE_EXISTING_STATUSES:
                    return JSONResponse(
                        status_code=409,
                        content={
                            "conflict": "queued",
                            "existing_task_id": existing["id"],
                            "message": f"Creator already has a queued task: {existing['id']}",
                        },
                    )
                if existing["status"] == TaskStatus.COMPLETED.value and existing["notes_count"] >= req.max_notes:
                    return JSONResponse(
                        status_code=409,
                        content={
                            "conflict": "completed",
                            "existing_notes": existing["notes_count"],
                            "existing_task_id": existing["id"],
                            "message": f"Creator already has {existing['notes_count']} notes.",
                        },
                    )
                if existing["status"] == TaskStatus.COMPLETED.value and existing["notes_count"] < req.max_notes:
                    await sdb.reset_task_for_resume(existing["id"], params)
                    await self._task_manager.requeue(existing["id"])
                    return {
                        "task_id": existing["id"],
                        "message": f"Resumed task from {existing['notes_count']} notes to target {req.max_notes}.",
                    }

        task_id = await self._task_manager.submit(TaskType.CREATOR.value, params, provider)
        return {"task_id": task_id, "provider": provider, "message": "Task created."}

    async def create_batch_creator_tasks(self, req: BatchCreatorTaskRequest):
        provider, common_params = self._request_params(req)
        await self._ensure_provider_ready(provider)
        if len(req.creator_urls) > settings.max_batch_tasks:
            raise HTTPException(400, f"Batch size exceeds MAX_BATCH_TASKS={settings.max_batch_tasks}.")
        task_ids: List[int] = []
        resumed = 0
        skipped = 0
        for creator_input in req.creator_urls:
            creator_input = creator_input.strip()
            if not creator_input:
                continue
            params = {"creator_input": creator_input, "max_notes": req.max_notes}
            if "provider_options" in common_params:
                params["provider_options"] = common_params["provider_options"]
            existing = await sdb.find_latest_creator_task(
                creator_input,
                provider,
                params if provider == sdb.TaskProvider.JUSTONEAPI.value else None,
            )
            if existing:
                if (
                    existing["status"] == TaskStatus.PAUSED.value
                    and self._budget_exhausted(existing)
                ):
                    await sdb.reset_task_for_resume(existing["id"], params)
                    await self._task_manager.requeue(existing["id"])
                    task_ids.append(existing["id"])
                    resumed += 1
                    continue
                if existing["status"] in ACTIVE_EXISTING_STATUSES:
                    skipped += 1
                    continue
                if existing["status"] == TaskStatus.COMPLETED.value and existing["notes_count"] < req.max_notes:
                    await sdb.reset_task_for_resume(existing["id"], params)
                    await self._task_manager.requeue(existing["id"])
                    task_ids.append(existing["id"])
                    resumed += 1
                    continue
                if existing["status"] == TaskStatus.COMPLETED.value and existing["notes_count"] >= req.max_notes:
                    skipped += 1
                    continue
            task_id = await self._task_manager.submit(TaskType.CREATOR.value, params, provider)
            task_ids.append(task_id)
        return {
            "task_ids": task_ids,
            "count": len(task_ids),
            "resumed": resumed,
            "skipped": skipped,
            "provider": provider,
            "message": f"Created or resumed {len(task_ids)} tasks; skipped {skipped}.",
        }

    async def create_note_task(self, req: NoteTaskRequest):
        provider, request_params = self._request_params(req)
        await self._ensure_provider_ready(provider)
        if not req.notes:
            raise HTTPException(400, "Provide at least one note.")
        if len(req.notes) > settings.max_batch_tasks:
            raise HTTPException(400, f"Batch size exceeds MAX_BATCH_TASKS={settings.max_batch_tasks}.")
        params = {"notes": [n.model_dump() for n in req.notes]}
        if "max_comments" in req.model_fields_set:
            params["max_comments"] = req.max_comments
        if "include_replies" in req.model_fields_set:
            params["include_replies"] = req.include_replies
        if "provider_options" in request_params:
            params["provider_options"] = request_params["provider_options"]
        task_id = await self._task_manager.submit(TaskType.NOTE.value, params, provider)
        return {
            "task_id": task_id,
            "provider": provider,
            "message": f"Task created for {len(req.notes)} notes.",
        }

    async def list_tasks(self):
        tasks = await sdb.list_tasks()
        return await sdb.enrich_tasks_with_crawl_counts(tasks)

    async def get_task(self, task_id: int):
        task = await sdb.get_task(task_id)
        if not task:
            raise HTTPException(404, "Task not found.")
        enriched = await sdb.enrich_tasks_with_crawl_counts([task])
        return enriched[0]

    async def resume_task(self, task_id: int):
        task = await self.get_task(task_id)
        provider = task.get("provider") or sdb.TaskProvider.LOCAL.value
        await self._ensure_provider_ready(provider)
        if task.get("manual_resume_required"):
            raise HTTPException(
                409,
                "Task request budget is exhausted. Submit it again with a higher max_requests value.",
            )
        if task["status"] in (TaskStatus.PENDING.value, TaskStatus.RUNNING.value):
            raise HTTPException(409, "Task is already queued or running.")
        params: Dict = json.loads(task["params"])
        params.pop("force", None)
        await sdb.reset_task_for_resume(task_id, params)
        await self._task_manager.requeue(task_id)
        return {"message": f"Task {task_id} has been requeued for resume."}

    async def recrawl_task(self, task_id: int):
        task = await self.get_task(task_id)
        provider = task.get("provider") or sdb.TaskProvider.LOCAL.value
        await self._ensure_provider_ready(provider)
        if task["status"] in (TaskStatus.PENDING.value, TaskStatus.RUNNING.value):
            raise HTTPException(409, "Task is already queued or running.")
        if task["task_type"] == TaskType.NOTE.value:
            raise HTTPException(400, "Note tasks do not support recrawl.")
        params: Dict = json.loads(task["params"])
        params["force"] = True
        await sdb.reset_task_for_resume(task_id, params, clear_checkpoint=True)
        await self._task_manager.requeue(task_id)
        return {"message": f"Task {task_id} has been requeued for recrawl."}
