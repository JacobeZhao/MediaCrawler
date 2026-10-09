import os
import tempfile
import unittest
from datetime import datetime, timedelta

import aiosqlite

from service import service_db as db


class ServiceDbProviderTaskTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._original_path = db.SERVICE_DB_PATH
        self._original_content_path = db.SQLITE_DB_PATH
        self._temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db.SERVICE_DB_PATH = os.path.join(self._temp_dir.name, "service.db")
        db.SQLITE_DB_PATH = os.path.join(self._temp_dir.name, "content.db")
        await db.init_service_db()

    async def asyncTearDown(self):
        db.SERVICE_DB_PATH = self._original_path
        db.SQLITE_DB_PATH = self._original_content_path
        self._temp_dir.cleanup()

    async def test_batch_delete_is_atomic_and_preserves_unrelated_rows(self):
        first = await db.create_task(db.TaskType.SEARCH, {"keyword": "first"})
        second = await db.create_task(db.TaskType.SEARCH, {"keyword": "second"})
        active = await db.create_task(db.TaskType.SEARCH, {"keyword": "active"})
        await db.update_task_status(first, db.TaskStatus.COMPLETED)
        await db.update_task_status(second, db.TaskStatus.FAILED)
        async with aiosqlite.connect(db.SERVICE_DB_PATH) as connection:
            await connection.execute(
                "INSERT INTO provider_requests (task_id, provider, endpoint, created_at) VALUES (?,?,?,?)",
                (first, "local", "search", "now"),
            )
            await connection.execute(
                "INSERT INTO crawl_events (task_id, event_type, created_at) VALUES (?,?,?)",
                (first, "test", "now"),
            )
            await connection.commit()

        with self.assertRaises(RuntimeError):
            await db.delete_tasks([first, active])
        self.assertIsNotNone(await db.get_task(first))
        with self.assertRaises(LookupError):
            await db.delete_tasks([first, 999999])
        self.assertIsNotNone(await db.get_task(first))
        self.assertEqual([first, second], await db.delete_tasks([first, second]))
        self.assertIsNone(await db.get_task(first))
        self.assertIsNone(await db.get_task(second))
        self.assertIsNotNone(await db.get_task(active))
        async with aiosqlite.connect(db.SERVICE_DB_PATH) as connection:
            for table in ("provider_requests", "crawl_events"):
                cursor = await connection.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE task_id=?", (first,)
                )
                self.assertEqual(0, (await cursor.fetchone())[0])

    async def test_paused_task_cannot_be_deleted(self):
        task_id = await db.create_task(db.TaskType.SEARCH, {"keyword": "paused"})
        await db.update_task_status(task_id, db.TaskStatus.PAUSED)
        with self.assertRaises(RuntimeError):
            await db.delete_tasks([task_id])
        self.assertIsNotNone(await db.get_task(task_id))

    async def test_status_counts_cover_all_tasks_not_just_list_limit(self):
        self.assertEqual({}, await db.get_task_status_counts())
        ids = [
            await db.create_task(db.TaskType.SEARCH, {"keyword": f"count-{index}"})
            for index in range(101)
        ]
        await db.update_task_status(ids[0], db.TaskStatus.COMPLETED)
        await db.update_task_status(ids[1], db.TaskStatus.FAILED)
        self.assertEqual(100, len(await db.list_tasks()))
        self.assertEqual(
            {"pending": 99, "completed": 1, "failed": 1},
            await db.get_task_status_counts(),
        )
        await db.delete_tasks([ids[0], ids[1]])
        self.assertEqual({"pending": 99}, await db.get_task_status_counts())

    async def test_resume_reset_rejects_missing_or_changed_task(self):
        task_id = await db.create_task(db.TaskType.SEARCH, {"keyword": "reset"})
        await db.update_task_status(task_id, db.TaskStatus.COMPLETED)
        with self.assertRaises(RuntimeError):
            await db.reset_task_for_resume(
                task_id, {"keyword": "reset"}, expected_status=db.TaskStatus.PAUSED.value
            )
        self.assertEqual("completed", (await db.get_task(task_id))["status"])
        await db.delete_tasks([task_id])
        with self.assertRaises(LookupError):
            await db.reset_task_for_resume(
                task_id, {"keyword": "reset"}, expected_status=db.TaskStatus.COMPLETED.value
            )

    def test_selected_task_ids_require_unique_positive_ints(self):
        self.assertEqual([1, 2], db.validate_task_ids([1, 2]))
        for invalid in ([], [1, 1], [0], [-1], [True], ["1"], None):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                db.validate_task_ids(invalid)

    async def test_dedupe_is_isolated_by_provider(self):
        params = {"keyword": "test", "max_notes": 20}

        local_id = await db.create_task(db.TaskType.SEARCH, params)
        duplicate_local_id = await db.create_task(db.TaskType.SEARCH, params)
        api_id = await db.create_task(
            db.TaskType.SEARCH,
            params,
            provider=db.TaskProvider.JUSTONEAPI,
        )

        self.assertEqual(local_id, duplicate_local_id)
        self.assertNotEqual(local_id, api_id)
        self.assertEqual((await db.get_task(local_id))["provider"], "local")
        self.assertEqual((await db.get_task(api_id))["provider"], "justoneapi")

    def test_justoneapi_scope_defaults_and_resume_controls_are_stable(self):
        base = {"keyword": "scope", "sort_type": "popularity_descending"}
        explicit_defaults = {
            **base,
            "provider_options": {
                "include_details": True,
                "include_comments": False,
                "include_replies": False,
                "max_pages": 3,
                "max_requests": 20,
                "note_type": "ALL",
                "time_filter": "ALL",
            },
        }
        base_key = db.task_scope_key(
            db.TaskType.SEARCH,
            base,
            db.TaskProvider.JUSTONEAPI,
        )
        self.assertEqual(
            base_key,
            db.task_scope_key(
                db.TaskType.SEARCH,
                explicit_defaults,
                db.TaskProvider.JUSTONEAPI,
            ),
        )

        scope_changes = {
            "include_details": False,
            "include_comments": True,
            "include_replies": True,
            "note_type": "VIDEO_NOTE",
            "time_filter": "ONE_WEEK",
        }
        for name, value in scope_changes.items():
            params = {
                **explicit_defaults,
                "provider_options": {
                    **explicit_defaults["provider_options"],
                    name: value,
                },
            }
            with self.subTest(name=name):
                self.assertNotEqual(
                    base_key,
                    db.task_scope_key(
                        db.TaskType.SEARCH,
                        params,
                        db.TaskProvider.JUSTONEAPI,
                    ),
                )

        for name, value in {"max_pages": 99, "max_requests": 999}.items():
            params = {
                **explicit_defaults,
                "provider_options": {
                    **explicit_defaults["provider_options"],
                    name: value,
                },
            }
            with self.subTest(name=name):
                self.assertEqual(
                    base_key,
                    db.task_scope_key(
                        db.TaskType.SEARCH,
                        params,
                        db.TaskProvider.JUSTONEAPI,
                    ),
                )

    async def test_pause_unfinished_tasks_only_updates_selected_provider(self):
        local_id = await db.create_task(db.TaskType.SEARCH, {"keyword": "local"})
        api_id = await db.create_task(
            db.TaskType.SEARCH,
            {"keyword": "api"},
            provider=db.TaskProvider.JUSTONEAPI,
        )

        paused_ids = await db.pause_unfinished_tasks(
            progress="provider disabled",
            provider=db.TaskProvider.JUSTONEAPI,
        )

        self.assertEqual(paused_ids, [api_id])
        self.assertEqual((await db.get_task(local_id))["status"], "pending")
        api_task = await db.get_task(api_id)
        self.assertEqual(api_task["status"], "paused")
        self.assertEqual(api_task["progress"], "provider disabled")

    async def test_restart_requeue_respects_provider_backoff(self):
        task_id = await db.create_task(
            db.TaskType.SEARCH,
            {"keyword": "backoff"},
            provider=db.TaskProvider.JUSTONEAPI,
        )
        self.assertTrue(await db.claim_task(task_id, "worker"))
        retry_at = (datetime.now() + timedelta(minutes=10)).isoformat()
        await db.update_task_status_if_owned(
            task_id,
            "worker",
            db.TaskStatus.PAUSED,
            retry_at=retry_at,
            lease_owner=None,
            lease_expires_at=None,
        )

        self.assertFalse(await db.claim_task(task_id, "early-worker"))

        queued = await db.requeue_unfinished_tasks(db.TaskProvider.JUSTONEAPI)

        self.assertEqual(queued, [])
        self.assertEqual((await db.get_task(task_id))["status"], "paused")

        await db.update_task_status(
            task_id,
            db.TaskStatus.PAUSED,
            retry_at=(datetime.now() - timedelta(seconds=1)).isoformat(),
        )
        queued = await db.requeue_unfinished_tasks(db.TaskProvider.JUSTONEAPI)
        self.assertEqual(queued, [task_id])
        self.assertEqual((await db.get_task(task_id))["status"], "pending")

    async def test_resume_preserves_checkpoint_and_recrawl_can_clear_it(self):
        task_id = await db.create_task(
            db.TaskType.SEARCH,
            {"keyword": "checkpoint", "max_notes": 20},
            provider=db.TaskProvider.JUSTONEAPI,
        )
        self.assertTrue(await db.claim_task(task_id, "worker"))
        self.assertTrue(
            await db.update_task_checkpoint(task_id, "worker", {"page": 2})
        )
        await db.update_task_status_if_owned(
            task_id,
            "worker",
            db.TaskStatus.FAILED,
            lease_owner=None,
            lease_expires_at=None,
        )

        await db.reset_task_for_resume(
            task_id,
            {"keyword": "checkpoint", "max_notes": 40},
        )
        self.assertEqual((await db.get_task(task_id))["checkpoint_json"], {"page": 2})

        await db.reset_task_for_resume(
            task_id,
            {"keyword": "checkpoint", "max_notes": 40, "force": True},
            clear_checkpoint=True,
        )
        task = await db.get_task(task_id)
        self.assertIsNone(task["checkpoint_json"])
        self.assertEqual(task["provider"], "justoneapi")

    async def test_startup_recovery_does_not_steal_an_active_lease(self):
        task_id = await db.create_task(
            db.TaskType.SEARCH,
            {"keyword": "active-worker"},
            provider=db.TaskProvider.JUSTONEAPI,
        )
        self.assertTrue(await db.claim_task(task_id, "active-worker", lease_seconds=300))

        queued = await db.requeue_unfinished_tasks(db.TaskProvider.JUSTONEAPI)
        paused = await db.pause_unfinished_tasks(
            provider=db.TaskProvider.JUSTONEAPI,
        )

        self.assertEqual(queued, [])
        self.assertEqual(paused, [])
        task = await db.get_task(task_id)
        self.assertEqual(task["status"], "running")
        self.assertEqual(task["lease_owner"], "active-worker")

    async def test_api_counts_use_task_attribution_while_local_keeps_legacy_counts(self):
        local_id = await db.create_task(db.TaskType.SEARCH, {"keyword": "shared"})
        api_id = await db.create_task(
            db.TaskType.SEARCH,
            {"keyword": "shared"},
            provider=db.TaskProvider.JUSTONEAPI,
        )
        async with aiosqlite.connect(db.SQLITE_DB_PATH) as content_db:
            await content_db.executescript(
                """
                CREATE TABLE xhs_note (note_id TEXT, source_keyword TEXT, user_id TEXT);
                CREATE TABLE xhs_note_comment (comment_id TEXT, note_id TEXT);
                CREATE TABLE xhs_content_source (
                    entity_type TEXT,
                    entity_id TEXT,
                    provider TEXT,
                    task_id INTEGER
                );
                INSERT INTO xhs_note VALUES ('n1', 'shared', 'u1');
                INSERT INTO xhs_note VALUES ('n2', 'shared', 'u2');
                INSERT INTO xhs_note VALUES ('n3', 'shared', 'u3');
                INSERT INTO xhs_note_comment VALUES ('c1', 'n1');
                INSERT INTO xhs_note_comment VALUES ('c2', 'n2');
                """
            )
            await content_db.executemany(
                "INSERT INTO xhs_content_source VALUES (?,?,?,?)",
                (
                    ("note", "n1", "justoneapi", api_id),
                    ("comment", "c1", "justoneapi", api_id),
                ),
            )
            await content_db.commit()

        tasks = await db.enrich_tasks_with_crawl_counts(
            [await db.get_task(local_id), await db.get_task(api_id)]
        )
        by_id = {task["id"]: task for task in tasks}

        self.assertEqual(by_id[local_id]["notes_count"], 3)
        self.assertEqual(by_id[local_id]["comments_count"], 2)
        self.assertEqual(by_id[api_id]["notes_count"], 1)
        self.assertEqual(by_id[api_id]["comments_count"], 1)

    async def test_expired_inflight_provider_request_stops_automatic_replay(self):
        task_id = await db.create_task(
            db.TaskType.SEARCH,
            {"keyword": "unknown"},
            provider=db.TaskProvider.JUSTONEAPI,
        )
        self.assertTrue(await db.claim_task(task_id, "crashed", lease_seconds=-1))
        await db.record_provider_request(
            task_id=task_id,
            provider=db.TaskProvider.JUSTONEAPI,
            endpoint="/search",
            request_state="inflight",
        )

        failed_ids = await db.fail_expired_tasks_with_inflight_provider_requests()

        self.assertEqual(failed_ids, [task_id])
        task = await db.get_task(task_id)
        self.assertEqual(task["status"], "failed")
        self.assertIn("outcome is unknown", task["error"])
        requests = await db.list_provider_requests(task_id)
        self.assertEqual(requests[0]["request_state"], "unknown")
        self.assertEqual(requests[0]["outcome_unknown"], 1)


if __name__ == "__main__":
    unittest.main()
