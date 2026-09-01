import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from service.crawler_engine import XHSCrawlerEngine, _safe_call
from service.executors.base import ExecutorLeaseLost


class LocalLeasePropagationTests(unittest.IsolatedAsyncioTestCase):
    async def test_safe_call_never_swallows_lease_loss(self):
        callback = AsyncMock(side_effect=ExecutorLeaseLost)

        with self.assertRaises(ExecutorLeaseLost):
            await _safe_call(callback, "progress")

    async def test_comment_callback_lease_loss_escapes_crawler_boundary(self):
        engine = object.__new__(XHSCrawlerEngine)
        engine._before_request = AsyncMock()

        async def crawl_comments(**kwargs):
            await kwargs["callback"]("note-1", [{"id": "comment-1"}])

        engine._xhs_client = type(
            "FakeClient",
            (),
            {"get_note_all_comments": staticmethod(crawl_comments)},
        )()
        progress = AsyncMock(side_effect=ExecutorLeaseLost)

        store_comments = AsyncMock()
        with (
            patch("service.crawler_engine.os.path.exists", return_value=False),
            patch(
                "service.crawler_engine.xhs_store.batch_update_xhs_note_comments",
                new=store_comments,
            ),
            self.assertRaises(ExecutorLeaseLost),
        ):
            await engine._fetch_and_store_comments(
                "note-1",
                "token",
                10,
                progress_cb=progress,
            )
        store_comments.assert_not_awaited()

    async def test_public_crawler_methods_keep_engine_ready_after_lease_loss(self):
        engine = object.__new__(XHSCrawlerEngine)
        engine._lock = asyncio.Lock()
        engine._do_search = AsyncMock(side_effect=ExecutorLeaseLost)
        engine._do_crawl_creator = AsyncMock(side_effect=ExecutorLeaseLost)
        engine._do_crawl_notes = AsyncMock(side_effect=ExecutorLeaseLost)

        calls = (
            lambda: engine.search_keyword("keyword"),
            lambda: engine.crawl_creator("creator"),
            lambda: engine.crawl_notes([]),
        )
        for call in calls:
            with self.subTest(call=call), self.assertRaises(ExecutorLeaseLost):
                await call()
            self.assertEqual(engine.status, "ready")
            self.assertEqual(engine.message, "Ready")


if __name__ == "__main__":
    unittest.main()
