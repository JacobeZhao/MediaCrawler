from fastapi import APIRouter, HTTPException

from ..dependencies import get_engine
from ..schemas.accounts import CookieRequest

router = APIRouter(prefix="/api/login")


@router.post("/cookie")
async def login_cookie(req: CookieRequest):
    engine = get_engine()
    ok = await engine.set_cookie(req.cookie)
    return {"success": ok, "message": engine.message}


@router.post("/qrcode")
async def login_qrcode():
    engine = get_engine()
    ok = await engine.trigger_qrcode_login()
    return {"success": ok, "message": engine.message}


@router.get("/qrcode/image")
async def get_default_qrcode_image():
    result = await get_engine().get_qrcode_for_web()
    if "error" in result:
        raise HTTPException(400, result["error"])
    return {"qrcode": result["qrcode"], "session_before": result["session_before"]}


@router.get("/qrcode/poll")
async def poll_default_qrcode(session_before: str = ""):
    return await get_engine().check_qrcode_login_done(session_before)
