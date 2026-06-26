from fastapi import APIRouter

from ..dependencies import get_engine, get_pool, get_task_manager

router = APIRouter()


@router.get("/api/status")
async def get_status():
    status = get_engine().get_status()
    status["queue_size"] = get_task_manager().queue_size()
    return status


@router.get("/healthz")
async def healthz():
    return {"status": "ok"}


@router.get("/readyz")
async def readyz():
    engine = get_engine()
    pool = get_pool()
    ready = engine.status == "ready" or pool.has_ready_engine()
    return {
        "status": "ok" if ready else "not_ready",
        "engine_status": engine.status,
        "ready_accounts": pool.ready_count(),
        "queue_size": get_task_manager().queue_size(),
    }


@router.get("/version")
async def version():
    return {"name": "xhs-crawler-service", "version": "1.0.0"}
