from typing import Optional

from fastapi import APIRouter, Query

from ..dependencies import get_note_query_service

router = APIRouter(prefix="/api/notes")


@router.get("")
async def list_notes(
    keyword: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    return await get_note_query_service().list_notes(keyword, user_id, limit, offset)


@router.get("/{note_id}/comments")
async def get_note_comments(note_id: str, limit: int = Query(default=200, ge=1, le=10000)):
    return await get_note_query_service().get_note_comments(note_id, limit)


@router.get("/{note_id}/images")
async def list_note_images(note_id: str):
    return get_note_query_service().list_note_images(note_id)
