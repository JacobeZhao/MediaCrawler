import os

from .settings import settings

SQLITE_DB_PATH = settings.sqlite_db_path
sqlite_db_config = {"db_path": SQLITE_DB_PATH}
