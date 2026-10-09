from fastapi import APIRouter

from .. import service_db as sdb
from ..circuit_breaker import circuit_breaker
from ..dependencies import get_engine, get_pool, get_task_manager
from ..rate_limiter import rate_limiter

router = APIRouter()


@router.get("/api/status")
async def get_status():
    status = get_engine().get_status()
    task_manager = get_task_manager()
    readiness = await task_manager.readiness()
    status["queue_size"] = task_manager.queue_size()
    status["providers"] = {
        provider: {
            **provider_status.as_dict(),
            "queue_size": task_manager.queue_size(provider),
        }
        for provider, provider_status in readiness.items()
    }
    status["ready_accounts"] = get_pool().ready_count()
    status["task_counts"] = await sdb.get_task_status_counts()
    status["circuit_breaker"] = circuit_breaker.status()
    status["rate_limiter"] = rate_limiter.snapshot()
    status["recent_events"] = await sdb.list_recent_crawl_events(limit=10)
    return status


@router.get("/healthz")
async def healthz():
    return {"status": "ok"}


@router.get("/readyz")
async def readyz():
    engine = get_engine()
    pool = get_pool()
    task_manager = get_task_manager()
    readiness = await task_manager.readiness()
    ready = any(provider_status.ready for provider_status in readiness.values())
    return {
        "status": "ok" if ready else "not_ready",
        "engine_status": engine.status,
        "ready_accounts": pool.ready_count(),
        "queue_size": task_manager.queue_size(),
        "providers": {
            provider: provider_status.as_dict()
            for provider, provider_status in readiness.items()
        },
    }


@router.get("/version")
async def version():
    return {"name": "xhs-crawler-service", "version": "1.0.0"}
