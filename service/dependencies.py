import os

import config as cfg

from .account_pool import AccountPool
from .crawler_engine import XHSCrawlerEngine
from .services.account_service import AccountService, QrSessionService
from .services.export_service import ExportService
from .services.note_service import NoteQueryService
from .services.proxy_service import ProxyService
from .services.task_service import TaskService
from .task_manager import TaskManager

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
IMAGE_DIR = os.path.join(ROOT_DIR, "data", "xhs", "images")

# Keep the current single-platform service contract explicit at startup.
cfg.SAVE_DATA_OPTION = "sqlite"
cfg.PLATFORM = "xhs"
cfg.ENABLE_GET_COMMENTS = True

engine = XHSCrawlerEngine()
pool = AccountPool(default_engine=engine)
task_manager = TaskManager(pool)
qr_sessions = QrSessionService(ROOT_DIR)
account_service = AccountService(pool, qr_sessions, task_manager)
task_service = TaskService(engine, task_manager)
note_query_service = NoteQueryService(IMAGE_DIR)
export_service = ExportService(IMAGE_DIR)
proxy_service = ProxyService()


def get_engine() -> XHSCrawlerEngine:
    return engine


def get_pool() -> AccountPool:
    return pool


def get_task_manager() -> TaskManager:
    return task_manager


def get_account_service() -> AccountService:
    return account_service


def get_task_service() -> TaskService:
    return task_service


def get_note_query_service() -> NoteQueryService:
    return note_query_service


def get_export_service() -> ExportService:
    return export_service


def get_proxy_service() -> ProxyService:
    return proxy_service
