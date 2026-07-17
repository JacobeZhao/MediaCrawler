import os

import config as cfg
from config.settings import settings

from .account_pool import AccountPool
from .crawler_engine import XHSCrawlerEngine
from .executors.justoneapi import JustOneApiTaskExecutor
from .executors.local import LocalTaskExecutor
from .executors.registry import ExecutorRegistry
from .providers.justoneapi.client import JustOneApiClient
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
justoneapi_client = JustOneApiClient(
    settings.justoneapi_token,
    base_url=settings.justoneapi_base_url,
    timeout_sec=settings.justoneapi_timeout_sec,
    max_retries=settings.justoneapi_max_retries,
    retry_base_sec=settings.justoneapi_retry_base_sec,
)
executor_registry = ExecutorRegistry(
    [
        LocalTaskExecutor(pool, enabled=settings.local_crawler_enabled),
        JustOneApiTaskExecutor(
            justoneapi_client,
            enabled=settings.justoneapi_enabled,
            max_requests_per_task=settings.justoneapi_max_requests_per_task,
        ),
    ]
)
task_manager = TaskManager(executor_registry)
qr_sessions = QrSessionService(ROOT_DIR)
account_service = AccountService(pool, qr_sessions, task_manager)
task_service = TaskService(task_manager)
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
