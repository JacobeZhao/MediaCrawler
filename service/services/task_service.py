import json
from typing import Dict, List

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from ..schemas.tasks import (
    BatchCreatorTaskRequest,
    BatchSearchTaskRequest,
    CreatorTaskRequest,
    NoteTaskRequest,
    SearchTaskRequest,
)

from ..crawler_engine import XHSCrawlerEngine
from .. import service_db as sdb
from ..task_manager import TaskManager

TaskStatus = sdb.TaskStatus
TaskType = sdb.TaskType


class TaskService:
    def __init__(self, engine: XHSCrawlerEngine, task_manager: TaskManager):
        self._engine = engine
        self._task_manager = task_manager

    def _ensure_engine_started(self):
        if self._engine.status == "stopped":
            raise HTTPException(503, "Crawler engine is not started.")

    async def create_search_task(self, req: SearchTaskRequest):
        self._ensure_engine_started()
        params = req.model_dump()

        if not req.force:
            existing = await sdb.find_latest_search_task(req.keyword)
            if existing:
                if existing["status"] in (TaskStatus.PENDING.value, TaskStatus.RUNNING.value):
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

        task_id = await self._task_manager.submit(TaskType.SEARCH.value, params)
        return {"task_id": task_id, "message": "Task created."}

    async def create_batch_search_tasks(self, req: BatchSearchTaskRequest):
        self._ensure_engine_started()
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
            existing = await sdb.find_latest_search_task(kw)
            if existing:
                if existing["status"] in (TaskStatus.PENDING.value, TaskStatus.RUNNING.value):
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
            task_id = await self._task_manager.submit(TaskType.SEARCH.value, params)
            task_ids.append(task_id)

        return {
            "task_ids": task_ids,
            "count": len(task_ids),
            "resumed": resumed,
            "skipped": skipped,
            "message": f"Created or resumed {len(task_ids)} tasks; skipped {skipped}.",
        }

    async def create_creator_task(self, req: CreatorTaskRequest):
        self._ensure_engine_started()
        params = req.model_dump()

        if not req.force:
            existing = await sdb.find_latest_creator_task(req.creator_input)
            if existing:
                if existing["status"] in (TaskStatus.PENDING.value, TaskStatus.RUNNING.value):
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

        task_id = await self._task_manager.submit(TaskType.CREATOR.value, params)
        return {"task_id": task_id, "message": "Task created."}

    async def create_batch_creator_tasks(self, req: BatchCreatorTaskRequest):
        self._ensure_engine_started()
        task_ids: List[int] = []
        resumed = 0
        skipped = 0
        for creator_input in req.creator_urls:
            creator_input = creator_input.strip()
            if not creator_input:
                continue
            params = {"creator_input": creator_input, "max_notes": req.max_notes}
            existing = await sdb.find_latest_creator_task(creator_input)
            if existing:
                if existing["status"] in (TaskStatus.PENDING.value, TaskStatus.RUNNING.value):
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
            task_id = await self._task_manager.submit(TaskType.CREATOR.value, params)
            task_ids.append(task_id)
        return {
            "task_ids": task_ids,
            "count": len(task_ids),
            "resumed": resumed,
            "skipped": skipped,
            "message": f"Created or resumed {len(task_ids)} tasks; skipped {skipped}.",
        }

    async def create_note_task(self, req: NoteTaskRequest):
        self._ensure_engine_started()
        if not req.notes:
            raise HTTPException(400, "Provide at least one note.")
        params = {"notes": [n.model_dump() for n in req.notes]}
        task_id = await self._task_manager.submit(TaskType.NOTE.value, params)
        return {"task_id": task_id, "message": f"Task created for {len(req.notes)} notes."}

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
        self._ensure_engine_started()
        task = await self.get_task(task_id)
        if task["status"] in (TaskStatus.PENDING.value, TaskStatus.RUNNING.value):
            raise HTTPException(409, "Task is already queued or running.")
        params: Dict = json.loads(task["params"])
        params.pop("force", None)
        await sdb.reset_task_for_resume(task_id, params)
        await self._task_manager.requeue(task_id)
        return {"message": f"Task {task_id} has been requeued for resume."}

    async def recrawl_task(self, task_id: int):
        self._ensure_engine_started()
        task = await self.get_task(task_id)
        if task["status"] in (TaskStatus.PENDING.value, TaskStatus.RUNNING.value):
            raise HTTPException(409, "Task is already queued or running.")
        if task["task_type"] == TaskType.NOTE.value:
            raise HTTPException(400, "Note tasks do not support recrawl.")
        params: Dict = json.loads(task["params"])
        params["force"] = True
        await sdb.reset_task_for_resume(task_id, params)
        await self._task_manager.requeue(task_id)
        return {"message": f"Task {task_id} has been requeued for recrawl."}
