import os
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from service.services.account_service import QrSessionService


class QrSessionServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_expires_session_and_removes_profile(self):
        with tempfile.TemporaryDirectory() as root:
            service = QrSessionService(root, ttl_seconds=1)
            session_id = "expired"
            profile = os.path.join(root, "browser_data", f"qr_session_{session_id}")
            os.makedirs(profile)
            engine = AsyncMock()
            service._sessions[session_id] = {
                "engine": engine,
                "created_at": time.monotonic() - 2,
            }

            with self.assertRaises(HTTPException) as raised:
                await service.get(session_id)

            self.assertEqual(raised.exception.status_code, 404)
            engine.stop.assert_awaited_once()
            self.assertFalse(os.path.exists(profile))

    async def test_close_all_stops_every_unadopted_session(self):
        with tempfile.TemporaryDirectory() as root:
            service = QrSessionService(root)
            engines = [AsyncMock(), AsyncMock()]
            for index, engine in enumerate(engines):
                service._sessions[str(index)] = {
                    "engine": engine,
                    "created_at": time.monotonic(),
                }

            await service.close_all()

            self.assertEqual(service._sessions, {})
            for engine in engines:
                engine.stop.assert_awaited_once()

    async def test_start_failure_removes_unregistered_profile(self):
        with tempfile.TemporaryDirectory() as root:
            service = QrSessionService(root)

            class FailingEngine:
                def __init__(self, *, user_data_dir, **kwargs):
                    self.user_data_dir = user_data_dir
                    os.makedirs(user_data_dir)
                    self.stop = AsyncMock(side_effect=RuntimeError("stop failed"))

                async def start(self):
                    return None

                async def get_qrcode_for_web(self):
                    return {"error": "QR failed"}

            with (
                patch(
                    "service.services.account_service.XHSCrawlerEngine",
                    FailingEngine,
                ),
                self.assertRaises(HTTPException),
            ):
                await service.start("account")

            self.assertEqual(service._sessions, {})
            profile_root = os.path.join(root, "browser_data")
            self.assertEqual(os.listdir(profile_root), [])

    async def test_forget_preserves_adopted_profile(self):
        with tempfile.TemporaryDirectory() as root:
            service = QrSessionService(root)
            session_id = "adopted"
            profile = os.path.join(root, "browser_data", f"qr_session_{session_id}")
            os.makedirs(profile)
            engine = AsyncMock()
            service._sessions[session_id] = {
                "engine": engine,
                "created_at": time.monotonic(),
            }

            service.forget(session_id)
            await service.close_all()

            engine.stop.assert_not_awaited()
            self.assertTrue(os.path.isdir(profile))


if __name__ == "__main__":
    unittest.main()
