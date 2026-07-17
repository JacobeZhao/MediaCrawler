import os
from contextlib import asynccontextmanager

from .runtime_env import load_root_env

load_root_env()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from config.settings import settings
from database.db_session import create_tables

from . import service_db as sdb
from .dependencies import (
    IMAGE_DIR,
    STATIC_DIR,
    engine,
    justoneapi_client,
    pool,
    task_manager,
)
from .routes import accounts, export, login, notes, proxies, status, tasks
from .runtime_lock import RuntimeLock


@asynccontextmanager
async def lifespan(app: FastAPI):
    runtime_lock = RuntimeLock()
    runtime_lock.acquire()
    app.state.runtime_lock = runtime_lock
    try:
        await sdb.init_service_db()
        os.makedirs(os.path.dirname(os.path.abspath(settings.sqlite_db_path)), exist_ok=True)
        await create_tables("sqlite")
        if settings.local_crawler_enabled:
            await engine.start()
            await pool.start()
        await task_manager.start()
        yield
    finally:
        await task_manager.stop()
        await justoneapi_client.aclose()
        await pool.stop()
        await engine.stop()
        runtime_lock.release()


def create_app() -> FastAPI:
    app = FastAPI(title="XHS Crawler Service", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(status.router)
    app.include_router(login.router)
    app.include_router(accounts.router)
    app.include_router(proxies.router)
    app.include_router(tasks.router)
    app.include_router(notes.router)
    app.include_router(export.router)

    os.makedirs(IMAGE_DIR, exist_ok=True)
    app.mount("/images", StaticFiles(directory=IMAGE_DIR), name="note-images")
    if os.path.isdir(STATIC_DIR):
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        path = os.path.join(STATIC_DIR, "index.html")
        if os.path.exists(path):
            return FileResponse(path)
        return HTMLResponse("<h1>Frontend not found</h1>")

    return app
