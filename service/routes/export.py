from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..dependencies import get_export_service

router = APIRouter(prefix="/api/export")


@router.get("/notes")
async def export_notes():
    try:
        buf = await get_export_service().build_tagged_notes_workbook()
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc

    filename = quote("xhs_notes_export.xlsx")
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )
