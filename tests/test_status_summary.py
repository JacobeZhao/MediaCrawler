import unittest
from unittest.mock import AsyncMock, Mock, patch

from service.routes import status


class StatusSummaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_status_includes_full_task_counts(self):
        engine = Mock()
        engine.get_status.return_value = {"status": "need_login"}
        manager = Mock()
        manager.readiness = AsyncMock(return_value={})
        manager.queue_size.return_value = 0
        pool = Mock()
        pool.ready_count.return_value = 0
        counts = {"pending": 4, "completed": 2, "failed": 1}

        with (
            patch.object(status, "get_engine", return_value=engine),
            patch.object(status, "get_task_manager", return_value=manager),
            patch.object(status, "get_pool", return_value=pool),
            patch.object(status.sdb, "get_task_status_counts", new_callable=AsyncMock, return_value=counts),
            patch.object(status.sdb, "list_recent_crawl_events", new_callable=AsyncMock, return_value=[]),
            patch.object(status.circuit_breaker, "status", return_value={}),
            patch.object(status.rate_limiter, "snapshot", return_value={}),
        ):
            result = await status.get_status()

        self.assertEqual(counts, result["task_counts"])
        self.assertEqual("need_login", result["status"])
        self.assertEqual(0, result["queue_size"])


if __name__ == "__main__":
    unittest.main()
