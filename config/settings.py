import os
from dataclasses import dataclass, field


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.lower() in ("1", "true", "yes", "on")


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return float(raw)


ROOT_DIR = os.path.dirname(os.path.dirname(__file__))


@dataclass(frozen=True)
class Settings:
    app_name: str = "xhs-crawler-service"
    version: str = "1.0.0"

    host: str = os.environ.get("HOST", "0.0.0.0")
    port: int = _int_env("PORT", 8088)
    reload: bool = _bool_env("RELOAD", False)

    platform: str = "xhs"
    save_data_option: str = os.environ.get("SAVE_DATA_OPTION", "sqlite")
    xhs_international: bool = _bool_env("XHS_INTERNATIONAL", False)

    headless: bool = _bool_env("HEADLESS", False)
    cdp_connect_existing: bool = _bool_env("CDP_CONNECT_EXISTING", True)
    local_crawler_enabled: bool = _bool_env("LOCAL_CRAWLER_ENABLED", True)

    sqlite_db_path: str = os.environ.get(
        "SQLITE_DB_PATH",
        os.path.join(ROOT_DIR, "database", "sqlite_tables.db"),
    )
    service_db_path: str = os.environ.get(
        "SERVICE_DB_PATH",
        os.path.join(ROOT_DIR, "data", "service.db"),
    )
    runtime_lock_path: str = os.environ.get(
        "RUNTIME_LOCK_PATH",
        os.path.join(ROOT_DIR, "data", "service.lock"),
    )

    crawler_min_sleep_sec: int = _int_env("CRAWLER_MIN_SLEEP_SEC", 3)
    crawler_max_sleep_sec: int = _int_env("CRAWLER_MAX_SLEEP_SEC", 7)
    crawler_global_min_interval_sec: float = _float_env("CRAWLER_GLOBAL_MIN_INTERVAL_SEC", 2.0)
    crawler_account_min_interval_sec: float = _float_env("CRAWLER_ACCOUNT_MIN_INTERVAL_SEC", 8.0)
    crawler_search_min_interval_sec: float = _float_env("CRAWLER_SEARCH_MIN_INTERVAL_SEC", 10.0)
    crawler_detail_min_interval_sec: float = _float_env("CRAWLER_DETAIL_MIN_INTERVAL_SEC", 8.0)
    crawler_comment_min_interval_sec: float = _float_env("CRAWLER_COMMENT_MIN_INTERVAL_SEC", 12.0)
    crawler_creator_min_interval_sec: float = _float_env("CRAWLER_CREATOR_MIN_INTERVAL_SEC", 12.0)
    crawler_task_start_jitter_min_sec: float = _float_env("CRAWLER_TASK_START_JITTER_MIN_SEC", 3.0)
    crawler_task_start_jitter_max_sec: float = _float_env("CRAWLER_TASK_START_JITTER_MAX_SEC", 18.0)
    crawler_account_request_budget: int = _int_env("CRAWLER_ACCOUNT_REQUEST_BUDGET", 35)
    crawler_account_budget_rest_min_sec: float = _float_env("CRAWLER_ACCOUNT_BUDGET_REST_MIN_SEC", 45.0)
    crawler_account_budget_rest_max_sec: float = _float_env("CRAWLER_ACCOUNT_BUDGET_REST_MAX_SEC", 180.0)
    crawler_risk_backoff_sec: float = _float_env("CRAWLER_RISK_BACKOFF_SEC", 900.0)
    crawler_task_max_notes_per_task: int = _int_env("CRAWLER_TASK_MAX_NOTES_PER_TASK", 200)
    crawler_task_max_comments_per_note: int = _int_env("CRAWLER_TASK_MAX_COMMENTS_PER_NOTE", 10000)
    crawler_max_notes_count: int = _int_env("CRAWLER_MAX_NOTES_COUNT", 15)
    crawler_max_comments_count_single_note: int = _int_env("CRAWLER_MAX_COMMENTS_COUNT_SINGLE_NOTE", 10)
    account_cooldown_base_sec: int = _int_env("ACCOUNT_COOLDOWN_BASE_SEC", 600)
    account_cooldown_max_sec: int = _int_env("ACCOUNT_COOLDOWN_MAX_SEC", 43200)
    account_health_check_interval_sec: int = _int_env("ACCOUNT_HEALTH_CHECK_INTERVAL_SEC", 900)
    task_pause_on_account_error: bool = _bool_env("TASK_PAUSE_ON_ACCOUNT_ERROR", True)
    circuit_window_sec: int = _int_env("CIRCUIT_WINDOW_SEC", 600)
    circuit_pause_sec: int = _int_env("CIRCUIT_PAUSE_SEC", 3600)
    circuit_error_threshold: int = _int_env("CIRCUIT_ERROR_THRESHOLD", 3)
    task_max_account_switches: int = _int_env("TASK_MAX_ACCOUNT_SWITCHES", 1)
    task_max_runtime_sec: int = _int_env("TASK_MAX_RUNTIME_SEC", 7200)
    max_queue_size: int = _int_env("MAX_QUEUE_SIZE", 200)
    max_batch_tasks: int = _int_env("MAX_BATCH_TASKS", 50)

    justoneapi_enabled: bool = _bool_env("JUSTONEAPI_ENABLED", False)
    justoneapi_token: str = field(
        default=os.environ.get("JUSTONEAPI_TOKEN", "").strip(),
        repr=False,
    )
    justoneapi_base_url: str = os.environ.get(
        "JUSTONEAPI_BASE_URL",
        "https://api.justoneapi.com",
    ).rstrip("/")
    justoneapi_timeout_sec: float = _float_env("JUSTONEAPI_TIMEOUT_SEC", 120.0)
    justoneapi_max_retries: int = _int_env("JUSTONEAPI_MAX_RETRIES", 2)
    justoneapi_retry_base_sec: float = _float_env("JUSTONEAPI_RETRY_BASE_SEC", 2.0)
    justoneapi_max_requests_per_task: int = _int_env(
        "JUSTONEAPI_MAX_REQUESTS_PER_TASK",
        100,
    )


settings = Settings()
