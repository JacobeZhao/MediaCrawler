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
            self._lock()
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
            self._unlock()
        finally:
            self._handle.close()
            self._handle = None

    def _lock(self):
        self._handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
            return
        import fcntl

        fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock(self):
        self._handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            return
        import fcntl

        fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
