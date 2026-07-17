import os
import tempfile
import unittest
from collections import defaultdict

from service import service_db as db
from service.executors.base import ExecutionContext, ExecutorPaused
from service.executors.justoneapi import JustOneApiTaskExecutor
from service.providers.justoneapi.models import ApiEnvelope
from service.providers.justoneapi.normalizer import JustOneApiNormalizer


def api_envelope(endpoint, data, *, code=0, request_id="request-1"):
    return ApiEnvelope(
        code=code,
        message="ok" if code == 0 else "limited",
        data=data,
        record_time="2026-07-14T12:00:00+08:00",
        request_id=request_id,
        endpoint=endpoint,
        http_status=200,
        duration_ms=10,
        attempt=1,
    )


class FakeClient:
    configured = True
    closed = False
    base_url = "https://api.justoneapi.com"
    timeout_sec = 120.0

    def __init__(self):
        self.responses = defaultdict(list)

    async def _next(self, name, *, observer, before_request):
        endpoint = f"/{name}"
        await before_request(endpoint, 1)
        envelope = self.responses[name].pop(0)
        await observer(envelope.request_record())
        return envelope

    async def search_notes(self, *args, observer=None, before_request=None, **kwargs):
        return await self._next(
            "search",
            observer=observer,
            before_request=before_request,
        )

    async def note_detail(self, *args, observer=None, before_request=None, **kwargs):
        return await self._next(
            "detail",
            observer=observer,
            before_request=before_request,
        )

    async def creator_notes(self, *args, observer=None, before_request=None, **kwargs):
        return await self._next(
            "creator_notes",
            observer=observer,
            before_request=before_request,
        )

    async def user_profile(self, *args, observer=None, before_request=None, **kwargs):
        return await self._next(
            "profile",
            observer=observer,
            before_request=before_request,
        )

    async def comments(self, *args, observer=None, before_request=None, **kwargs):
        return await self._next(
            "comments",
            observer=observer,
            before_request=before_request,
        )

    async def replies(self, *args, observer=None, before_request=None, **kwargs):
        return await self._next(
            "replies",
            observer=observer,
            before_request=before_request,
        )

    async def resolve_share_link(self, *args, observer=None, before_request=None, **kwargs):
        return await self._next(
            "resolve",
            observer=observer,
            before_request=before_request,
        )

    async def aclose(self):
        self.closed = True


class FakeStore:
    def __init__(self):
        self.notes = []
        self.comments = []
        self.creators = []

    async def store_content(self, item, **metadata):
        self.notes.append((item, metadata))

    async def store_comment(self, item, **metadata):
        self.comments.append((item, metadata))

    async def store_creator(self, item, **metadata):
        self.creators.append((item, metadata))


class JustOneApiExecutorTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._original_path = db.SERVICE_DB_PATH
        self._temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db.SERVICE_DB_PATH = os.path.join(self._temp_dir.name, "service.db")
        await db.init_service_db()
        self.progress = []
        self.checkpoints = []

    async def asyncTearDown(self):
        db.SERVICE_DB_PATH = self._original_path
        self._temp_dir.cleanup()

    def context(self):
        async def progress_callback(**kwargs):
            self.progress.append(kwargs)
            return True

        async def checkpoint_callback(value):
            self.checkpoints.append(value)
            return True

        return ExecutionContext(
            task_id=42,
            progress_callback=progress_callback,
            checkpoint_callback=checkpoint_callback,
        )

    async def test_search_enriches_stores_audits_and_checkpoints(self):
        client = FakeClient()
        client.responses["search"].append(
            api_envelope(
                "/search",
                {
                    "items": [
                        {
                            "id": "note-1",
                            "noteCard": {
                                "displayTitle": "summary",
                                "user": {"userId": "user-1"},
                                "interactInfo": {"likedCount": 0},
                            },
                        }
                    ],
                    "hasMore": False,
                },
                request_id="search-request",
            )
        )
        client.responses["detail"].append(
            api_envelope(
                "/detail",
                {"noteId": "note-1", "title": "full title", "desc": "body"},
                request_id="detail-request",
            )
        )
        store = FakeStore()
        executor = JustOneApiTaskExecutor(
            client,
            store=store,
            enabled=True,
            max_requests_per_task=10,
        )

        result = await executor.execute(
            {"task_type": "search", "checkpoint_json": None},
            {
                "keyword": "coffee",
                "max_notes": 1,
                "provider_options": {"max_pages": 2, "max_requests": 10},
            },
            self.context(),
        )

        self.assertEqual(result["notes_count"], 1)
        self.assertEqual(result["request_count"], 2)
        self.assertEqual(result["billed_success_count"], 2)
        self.assertFalse(result["budget_exhausted"])
        self.assertEqual([item[0]["title"] for item in store.notes], ["summary", "full title"])
        self.assertEqual(store.notes[0][1]["provider"], "justoneapi")
        self.assertEqual(store.notes[0][1]["task_id"], 42)
        self.assertEqual(self.checkpoints[-1]["note_ids"], ["note-1"])
        requests = await db.list_provider_requests(42)
        self.assertEqual(len(requests), 2)
        self.assertTrue(all(item["billed"] == 1 for item in requests))

    async def test_creator_resume_keeps_profile_and_provider_attribution(self):
        client = FakeClient()
        client.responses["profile"].append(
            api_envelope(
                "/profile",
                {
                    "basicInfo": {
                        "userId": "creator-1",
                        "nickname": "Creator One",
                    }
                },
                request_id="profile-request",
            )
        )
        client.responses["creator_notes"].extend(
            [
                api_envelope(
                    "/creator-notes",
                    {
                        "items": [{"id": "creator-note-1", "title": "first"}],
                        "hasMore": True,
                        "cursor": "creator-page-2",
                    },
                    request_id="creator-page-1-request",
                ),
                api_envelope(
                    "/creator-notes",
                    {
                        "items": [{"id": "creator-note-2", "title": "second"}],
                        "hasMore": False,
                    },
                    request_id="creator-page-2-request",
                ),
            ]
        )
        store = FakeStore()
        executor = JustOneApiTaskExecutor(
            client,
            store=store,
            enabled=True,
            max_requests_per_task=3,
        )
        params = {
            "creator_input": "creator-1",
            "max_notes": 2,
            "provider_options": {
                "include_details": False,
                "max_pages": 3,
                "max_requests": 2,
            },
        }

        first = await executor.execute(
            {"task_type": "creator", "checkpoint_json": None},
            params,
            self.context(),
        )
        checkpoint = dict(self.checkpoints[-1])
        self.assertTrue(first["budget_exhausted"])
        self.assertEqual(checkpoint["user_id"], "creator-1")
        self.assertTrue(checkpoint["profile_completed"])
        self.assertEqual(checkpoint["note_ids"], ["creator-note-1"])

        resumed_params = dict(params)
        resumed_params["provider_options"] = dict(params["provider_options"])
        resumed_params["provider_options"]["max_requests"] = 3
        second = await executor.execute(
            {"task_type": "creator", "checkpoint_json": checkpoint},
            resumed_params,
            self.context(),
        )

        self.assertFalse(second["budget_exhausted"])
        self.assertEqual(second["request_count"], 3)
        self.assertEqual(second["creators_count"], 1)
        self.assertEqual(second["notes_count"], 2)
        self.assertEqual(len(store.creators), 1)
        self.assertEqual(store.creators[0][1]["provider"], "justoneapi")
        self.assertEqual(store.creators[0][1]["task_id"], 42)
        self.assertEqual(
            [item[0]["note_id"] for item in store.notes],
            ["creator-note-1", "creator-note-2"],
        )
        self.assertTrue(
            all(metadata["provider"] == "justoneapi" for _, metadata in store.notes)
        )
        requests = await db.list_provider_requests(42)
        self.assertEqual(
            [item["request_id"] for item in requests],
            [
                "profile-request",
                "creator-page-1-request",
                "creator-page-2-request",
            ],
        )

    async def test_note_share_link_stores_tag_attribution_and_checkpoint(self):
        client = FakeClient()
        client.responses["resolve"].append(
            api_envelope(
                "/resolve",
                {"url": "https://www.xiaohongshu.com/explore/resolvednote"},
                request_id="resolve-request",
            )
        )
        client.responses["detail"].append(
            api_envelope(
                "/detail",
                {
                    "noteId": "resolvednote",
                    "title": "resolved title",
                    "desc": "resolved body",
                },
                request_id="resolved-detail-request",
            )
        )
        store = FakeStore()
        executor = JustOneApiTaskExecutor(
            client,
            store=store,
            enabled=True,
            max_requests_per_task=2,
        )

        result = await executor.execute(
            {"task_type": "note", "checkpoint_json": None},
            {
                "notes": [
                    {
                        "note_input": "https://xhslink.com/a/short-link",
                        "d_level": "D2",
                        "quality": "A",
                    }
                ],
                "provider_options": {"max_requests": 2},
            },
            self.context(),
        )

        self.assertFalse(result["budget_exhausted"])
        self.assertEqual(result["request_count"], 2)
        self.assertEqual(result["notes_count"], 1)
        self.assertEqual(store.notes[0][0]["note_id"], "resolvednote")
        self.assertEqual(store.notes[0][1]["provider"], "justoneapi")
        self.assertEqual(store.notes[0][1]["task_id"], 42)
        tags = await db.get_all_note_tags()
        self.assertEqual(tags["resolvednote"]["d_level"], "D2")
        self.assertEqual(tags["resolvednote"]["quality"], "A")
        self.assertEqual(self.checkpoints[-1]["kind"], "note")
        self.assertEqual(self.checkpoints[-1]["note_ids"], ["resolvednote"])
        requests = await db.list_provider_requests(42)
        self.assertEqual(
            [item["request_id"] for item in requests],
            ["resolve-request", "resolved-detail-request"],
        )

    async def test_request_budget_stops_before_detail_without_extra_call(self):
        client = FakeClient()
        client.responses["search"].append(
            api_envelope(
                "/search",
                {"items": [{"id": "note-1", "noteCard": {}}], "hasMore": False},
            )
        )
        store = FakeStore()
        executor = JustOneApiTaskExecutor(
            client,
            store=store,
            enabled=True,
            max_requests_per_task=1,
        )

        result = await executor.execute(
            {"task_type": "search", "checkpoint_json": None},
            {
                "keyword": "budget",
                "max_notes": 1,
                "provider_options": {"max_requests": 20, "include_details": True},
            },
            self.context(),
        )

        self.assertEqual(result["request_count"], 1)
        self.assertTrue(result["budget_exhausted"])
        self.assertEqual(result["notes_count"], 1)
        self.assertEqual(len(store.notes), 1)

    async def test_rate_limit_is_audited_and_pauses_provider(self):
        client = FakeClient()
        client.responses["search"].append(
            api_envelope("/search", {}, code=302, request_id="limited-request")
        )
        executor = JustOneApiTaskExecutor(
            client,
            store=FakeStore(),
            enabled=True,
        )

        with self.assertRaises(ExecutorPaused) as caught:
            await executor.execute(
                {"task_type": "search", "checkpoint_json": None},
                {"keyword": "limited"},
                self.context(),
            )

        self.assertEqual(caught.exception.retry_after_seconds, 60.0)
        self.assertFalse((await executor.readiness()).ready)
        requests = await db.list_provider_requests(42)
        self.assertEqual(requests[0]["business_code"], 302)
        self.assertEqual(requests[0]["billed"], 0)

    async def test_request_budget_persists_across_executor_attempts(self):
        client = FakeClient()
        client.responses["search"].append(
            api_envelope(
                "/search",
                {"items": [{"id": "note-1", "noteCard": {}}], "hasMore": True},
            )
        )
        executor = JustOneApiTaskExecutor(
            client,
            store=FakeStore(),
            enabled=True,
            max_requests_per_task=1,
        )
        params = {
            "keyword": "persistent-budget",
            "max_notes": 2,
            "provider_options": {
                "include_details": False,
                "max_pages": 3,
                "max_requests": 1,
            },
        }

        first = await executor.execute(
            {"task_type": "search", "checkpoint_json": None},
            params,
            self.context(),
        )
        persisted_checkpoint = dict(self.checkpoints[-1])
        second = await executor.execute(
            {"task_type": "search", "checkpoint_json": persisted_checkpoint},
            params,
            self.context(),
        )

        self.assertTrue(first["budget_exhausted"])
        self.assertTrue(second["budget_exhausted"])
        self.assertEqual(second["request_count"], 1)
        self.assertEqual(len(await db.list_provider_requests(42)), 1)

    async def test_resume_continues_comment_cursor_without_rebuying_note_detail(self):
        client = FakeClient()
        client.responses["detail"].append(
            api_envelope("/detail", {"noteId": "note-1", "title": "note"})
        )
        client.responses["comments"].append(
            api_envelope(
                "/comments",
                {
                    "comments": [{"id": "comment-1", "content": "first"}],
                    "hasMore": True,
                    "cursor": "next-page",
                },
                request_id="comment-page-1",
            )
        )
        store = FakeStore()
        executor = JustOneApiTaskExecutor(
            client,
            store=store,
            enabled=True,
            max_requests_per_task=4,
        )
        params = {
            "notes": [{"note_input": "note-1", "d_level": "D1", "quality": "A"}],
            "max_comments": 10,
            "provider_options": {
                "include_comments": True,
                "max_pages": 3,
                "max_requests": 2,
            },
        }

        first = await executor.execute(
            {"task_type": "note", "checkpoint_json": None},
            params,
            self.context(),
        )
        checkpoint = dict(self.checkpoints[-1])
        self.assertTrue(first["budget_exhausted"])
        self.assertEqual(checkpoint["comment_progress"]["note-1"]["cursor"], "next-page")

        client.responses["comments"].append(
            api_envelope(
                "/comments",
                {
                    "comments": [{"id": "comment-2", "content": "second"}],
                    "hasMore": False,
                },
                request_id="comment-page-2",
            )
        )
        resumed_params = dict(params)
        resumed_params["provider_options"] = dict(params["provider_options"])
        resumed_params["provider_options"]["max_requests"] = 4
        second = await executor.execute(
            {"task_type": "note", "checkpoint_json": checkpoint},
            resumed_params,
            self.context(),
        )

        self.assertFalse(second["budget_exhausted"])
        self.assertEqual(second["request_count"], 3)
        self.assertEqual(second["comments_count"], 2)
        self.assertEqual(len(store.notes), 1)
        self.assertEqual([item[0]["comment_id"] for item in store.comments], ["comment-1", "comment-2"])

    def test_legacy_provider_option_defaults_and_bounds_are_stable(self):
        self.assertEqual(
            JustOneApiTaskExecutor._options({}),
            {
                "include_details": True,
                "include_comments": False,
                "include_replies": False,
                "max_pages": 3,
                "max_requests": 20,
                "note_type": "ALL",
                "time_filter": "ALL",
            },
        )
        lower = JustOneApiTaskExecutor._options(
            {
                "provider_options": {
                    "include_details": 0,
                    "include_comments": 1,
                    "include_replies": "",
                    "max_pages": 0,
                    "max_requests": "invalid",
                }
            }
        )
        self.assertFalse(lower["include_details"])
        self.assertTrue(lower["include_comments"])
        self.assertFalse(lower["include_replies"])
        self.assertEqual(lower["max_pages"], 1)
        self.assertEqual(lower["max_requests"], 20)

        upper = JustOneApiTaskExecutor._options(
            {"provider_options": {"max_pages": 101, "max_requests": 1001}}
        )
        self.assertEqual(upper["max_pages"], 100)
        self.assertEqual(upper["max_requests"], 1000)

    def test_normalizer_preserves_explicit_zero_and_omits_missing_comment_count(self):
        note = JustOneApiNormalizer.note(
            {"id": "note-1", "interactInfo": {"likedCount": 0}}
        )
        missing = JustOneApiNormalizer.comment({"id": "c1"}, note_id="note-1")
        explicit = JustOneApiNormalizer.comment(
            {"id": "c2", "subCommentCount": 0},
            note_id="note-1",
        )

        self.assertEqual(note.liked_count, 0)
        self.assertIsNone(missing.sub_comment_count)
        self.assertEqual(explicit.sub_comment_count, 0)
        pagination = JustOneApiNormalizer.pagination(
            {
                "has_more": "false",
                "api_info": {"search_id": "search-1", "session_id": "session-1"},
            }
        )
        self.assertFalse(pagination["has_more"])
        self.assertEqual(pagination["search_id"], "search-1")
        self.assertEqual(pagination["session_id"], "session-1")


if __name__ == "__main__":
    unittest.main()
