from fastapi import APIRouter

from ..dependencies import get_task_service
from ..schemas.tasks import (
    BatchCreatorTaskRequest,
    BatchSearchTaskRequest,
    CreatorTaskRequest,
    NoteTaskRequest,
    SearchTaskRequest,
)

router = APIRouter(prefix="/api/tasks")


@router.post("/search")
async def create_search_task(req: SearchTaskRequest):
    return await get_task_service().create_search_task(req)


@router.post("/batch_search")
async def create_batch_search_tasks(req: BatchSearchTaskRequest):
    return await get_task_service().create_batch_search_tasks(req)


@router.post("/creator")
async def create_creator_task(req: CreatorTaskRequest):
    return await get_task_service().create_creator_task(req)


@router.post("/batch_creator")
async def create_batch_creator_tasks(req: BatchCreatorTaskRequest):
    return await get_task_service().create_batch_creator_tasks(req)


@router.post("/note")
async def create_note_task(req: NoteTaskRequest):
    return await get_task_service().create_note_task(req)


@router.get("")
async def list_tasks():
    return await get_task_service().list_tasks()


@router.get("/{task_id}")
async def get_task(task_id: int):
    return await get_task_service().get_task(task_id)


@router.post("/{task_id}/resume")
async def resume_task(task_id: int):
    return await get_task_service().resume_task(task_id)


@router.post("/{task_id}/recrawl")
async def recrawl_task(task_id: int):
    return await get_task_service().recrawl_task(task_id)
