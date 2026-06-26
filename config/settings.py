import os
from dataclasses import dataclass


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

    crawler_min_sleep_sec: int = _int_env("CRAWLER_MIN_SLEEP_SEC", 1)
    crawler_max_sleep_sec: int = _int_env("CRAWLER_MAX_SLEEP_SEC", 2)
    crawler_max_notes_count: int = _int_env("CRAWLER_MAX_NOTES_COUNT", 15)
    crawler_max_comments_count_single_note: int = _int_env("CRAWLER_MAX_COMMENTS_COUNT_SINGLE_NOTE", 10)


settings = Settings()
