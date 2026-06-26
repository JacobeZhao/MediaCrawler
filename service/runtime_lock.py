import os

from config.settings import settings


class RuntimeLock:
    """Single-process lock for local SQLite + Playwright profile deployment."""

    def __init__(self, path: str = settings.runtime_lock_path):
        self._path = path
        self._handle = None

    def acquire(self):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        self._handle = open(self._path, "a+", encoding="utf-8")
        try:
            import msvcrt

            self._handle.seek(0)
            msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            self._handle.close()
            self._handle = None
            raise RuntimeError(
                "Another XHS crawler service instance is already running for this runtime directory."
            ) from exc
        self._handle.seek(0)
        self._handle.truncate()
        self._handle.write(str(os.getpid()))
        self._handle.flush()

    def release(self):
        if not self._handle:
            return
        try:
            import msvcrt

            self._handle.seek(0)
            msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            self._handle.close()
            self._handle = None
