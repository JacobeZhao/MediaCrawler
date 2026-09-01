import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from service import main


class AppLifespanTests(unittest.IsolatedAsyncioTestCase):
    async def test_shutdown_disposes_database_engines_and_releases_runtime_lock(self):
        app = SimpleNamespace(state=SimpleNamespace())
        runtime_lock = Mock()

        with (
            patch.object(main, "RuntimeLock", return_value=runtime_lock),
            patch.object(main.sdb, "init_service_db", AsyncMock()),
            patch.object(main.os, "makedirs"),
            patch.object(main, "create_tables", AsyncMock()),
            patch.object(
                main,
                "settings",
                SimpleNamespace(
                    local_crawler_enabled=False,
                    sqlite_db_path="test.db",
                ),
            ),
            patch.object(main.task_manager, "start", AsyncMock()),
            patch.object(main.task_manager, "stop", AsyncMock()),
            patch.object(main.justoneapi_client, "aclose", AsyncMock()),
            patch.object(main.qr_sessions, "close_all", AsyncMock()) as close_qr,
            patch.object(main.pool, "stop", AsyncMock()),
            patch.object(main.engine, "stop", AsyncMock()),
            patch.object(main, "dispose_engines", AsyncMock()) as dispose_engines,
        ):
            async with main.lifespan(app):
                runtime_lock.acquire.assert_called_once_with()

        dispose_engines.assert_awaited_once_with()
        close_qr.assert_awaited_once_with()
        runtime_lock.release.assert_called_once_with()

    async def test_shutdown_cleanup_survives_component_stop_failure(self):
        app = SimpleNamespace(state=SimpleNamespace())
        runtime_lock = Mock()
        provider_close = AsyncMock()
        pool_stop = AsyncMock()
        engine_stop = AsyncMock()
        close_qr = AsyncMock()

        with (
            patch.object(main, "RuntimeLock", return_value=runtime_lock),
            patch.object(main.sdb, "init_service_db", AsyncMock()),
            patch.object(main.os, "makedirs"),
            patch.object(main, "create_tables", AsyncMock()),
            patch.object(
                main,
                "settings",
                SimpleNamespace(
                    local_crawler_enabled=False,
                    sqlite_db_path="test.db",
                ),
            ),
            patch.object(main.task_manager, "start", AsyncMock()),
            patch.object(
                main.task_manager,
                "stop",
                AsyncMock(side_effect=RuntimeError("stop failed")),
            ),
            patch.object(main.justoneapi_client, "aclose", provider_close),
            patch.object(main.qr_sessions, "close_all", close_qr),
            patch.object(main.pool, "stop", pool_stop),
            patch.object(main.engine, "stop", engine_stop),
            patch.object(main, "dispose_engines", AsyncMock()) as dispose_engines,
        ):
            with self.assertRaisesRegex(RuntimeError, "stop failed"):
                async with main.lifespan(app):
                    pass

        provider_close.assert_awaited_once_with()
        close_qr.assert_awaited_once_with()
        pool_stop.assert_awaited_once_with()
        engine_stop.assert_awaited_once_with()
        dispose_engines.assert_awaited_once_with()
        runtime_lock.release.assert_called_once_with()

    async def test_shutdown_continues_after_qr_cleanup_failure(self):
        app = SimpleNamespace(state=SimpleNamespace())
        runtime_lock = Mock()
        pool_stop = AsyncMock()
        engine_stop = AsyncMock()

        with (
            patch.object(main, "RuntimeLock", return_value=runtime_lock),
            patch.object(main.sdb, "init_service_db", AsyncMock()),
            patch.object(main.os, "makedirs"),
            patch.object(main, "create_tables", AsyncMock()),
            patch.object(
                main,
                "settings",
                SimpleNamespace(local_crawler_enabled=False, sqlite_db_path="test.db"),
            ),
            patch.object(main.task_manager, "start", AsyncMock()),
            patch.object(main.task_manager, "stop", AsyncMock()),
            patch.object(main.justoneapi_client, "aclose", AsyncMock()),
            patch.object(
                main.qr_sessions,
                "close_all",
                AsyncMock(side_effect=RuntimeError("QR cleanup failed")),
            ),
            patch.object(main.pool, "stop", pool_stop),
            patch.object(main.engine, "stop", engine_stop),
            patch.object(main, "dispose_engines", AsyncMock()) as dispose_engines,
        ):
            with self.assertRaisesRegex(RuntimeError, "QR cleanup failed"):
                async with main.lifespan(app):
                    pass

        pool_stop.assert_awaited_once_with()
        engine_stop.assert_awaited_once_with()
        dispose_engines.assert_awaited_once_with()
        runtime_lock.release.assert_called_once_with()
