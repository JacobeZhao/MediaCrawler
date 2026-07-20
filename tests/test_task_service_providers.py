import json
import os
import tempfile
import unittest

from fastapi import HTTPException

from service import service_db as db
from service.executors.base import ProviderReadiness
from pydantic import ValidationError

from service.schemas.tasks import (
    BatchSearchTaskRequest,
    JustOneApiOptions,
    SearchTaskRequest,
)
from service.services.task_service import TaskService


class FakeTaskManager:
    def __init__(self, readiness):
        self._readiness = readiness
        self.requeued = []

    async def provider_readiness(self, provider):
        if provider not in self._readiness:
            raise ValueError(f"Unknown task provider: {provider}")
        return self._readiness[provider]

    async def submit(self, task_type, params, provider="local"):
        return await db.create_task(task_type, params, provider=provider)

    async def requeue(self, task_id):
        self.requeued.append(task_id)


class TaskServiceProviderTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._original_path = db.SERVICE_DB_PATH
        self._temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db.SERVICE_DB_PATH = os.path.join(self._temp_dir.name, "service.db")
        await db.init_service_db()

    async def asyncTearDown(self):
        db.SERVICE_DB_PATH = self._original_path
        self._temp_dir.cleanup()

    async def test_legacy_request_defaults_to_local_and_can_queue_while_busy(self):
        manager = FakeTaskManager(
            {
                "local": ProviderReadiness(
                    enabled=True,
                    ready=False,
                    reason="no_ready_account",
                )
            }
        )
        service = TaskService(manager)

        response = await service.create_search_task(
            SearchTaskRequest(keyword="legacy")
        )

        task = await db.get_task(response["task_id"])
        self.assertEqual(task["provider"], "local")
        self.assertNotIn("provider_options", json.loads(task["params"]))

    async def test_justoneapi_request_stores_normalized_provider_options(self):
        manager = FakeTaskManager(
            {"justoneapi": ProviderReadiness(enabled=True, ready=True)}
        )
        service = TaskService(manager)

        response = await service.create_search_task(
            SearchTaskRequest(
                keyword="api",
                provider="justoneapi",
                provider_options=JustOneApiOptions(
                    include_comments=True,
                    max_pages=4,
                    max_requests=12,
                ),
            )
        )

        task = await db.get_task(response["task_id"])
        params = json.loads(task["params"])
        self.assertEqual(task["provider"], "justoneapi")
        self.assertEqual(params["provider_options"]["max_pages"], 4)
        self.assertTrue(params["provider_options"]["include_comments"])

    async def test_unconfigured_justoneapi_is_rejected(self):
        manager = FakeTaskManager(
            {
                "justoneapi": ProviderReadiness(
                    enabled=True,
                    ready=False,
                    reason="missing_token",
                )
            }
        )
        service = TaskService(manager)

        with self.assertRaises(HTTPException) as raised:
            await service.create_search_task(
                SearchTaskRequest(keyword="api", provider="justoneapi")
            )

        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("missing_token", str(raised.exception.detail))

    async def test_higher_budget_resubmission_resumes_manual_pause(self):
        manager = FakeTaskManager(
            {"justoneapi": ProviderReadiness(enabled=True, ready=True)}
        )
        service = TaskService(manager)
        initial = SearchTaskRequest(
            keyword="resume-budget",
            max_notes=10,
            provider="justoneapi",
            provider_options=JustOneApiOptions(max_requests=1),
        )
        _, initial_params = service._request_params(initial)
        task_id = await db.create_task(
            db.TaskType.SEARCH,
            initial_params,
            provider=db.TaskProvider.JUSTONEAPI,
        )
        await db.update_task_status(
            task_id,
            db.TaskStatus.PAUSED,
            result_data=json.dumps({"budget_exhausted": True}),
            checkpoint_json=json.dumps({"kind": "search", "request_count": 1}),
            manual_resume_required=1,
        )

        response = await service.create_search_task(
            SearchTaskRequest(
                keyword="resume-budget",
                max_notes=10,
                provider="justoneapi",
                provider_options=JustOneApiOptions(max_requests=5),
            )
        )

        self.assertEqual(response["task_id"], task_id)
        self.assertEqual(manager.requeued, [task_id])
        task = await db.get_task(task_id)
        self.assertEqual(task["status"], "pending")
        self.assertEqual(task["manual_resume_required"], 0)
        self.assertEqual(json.loads(task["params"])["provider_options"]["max_requests"], 5)
        self.assertEqual(task["checkpoint_json"]["request_count"], 1)

    def test_provider_options_reject_unknown_billing_controls(self):
        with self.assertRaises(ValidationError):
            JustOneApiOptions.model_validate({"max_request": 1})
        with self.assertRaises(ValidationError):
            SearchTaskRequest(
                keyword="invalid-days",
                provider="justoneapi",
                days_limit=7,
            )

    def test_provider_option_defaults_are_stable(self):
        self.assertEqual(
            JustOneApiOptions().model_dump(),
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

    def test_search_sort_defaults_are_provider_specific(self):
        self.assertEqual(
            SearchTaskRequest(keyword="local").sort_type,
            "popularity_descending",
        )
        self.assertEqual(
            SearchTaskRequest(keyword="api", provider="justoneapi").sort_type,
            "general",
        )
        self.assertEqual(
            BatchSearchTaskRequest(
                keywords=["api"],
                provider="justoneapi",
            ).sort_type,
            "general",
        )
        self.assertEqual(
            SearchTaskRequest(
                keyword="api",
                provider="justoneapi",
                sort_type="time_descending",
            ).sort_type,
            "time_descending",
        )

    async def test_search_filters_have_distinct_provider_scopes(self):
        manager = FakeTaskManager(
            {"justoneapi": ProviderReadiness(enabled=True, ready=True)}
        )
        service = TaskService(manager)

        all_time = await service.create_search_task(
            SearchTaskRequest(
                keyword="scope",
                provider="justoneapi",
                provider_options=JustOneApiOptions(time_filter="ALL"),
            )
        )
        one_week = await service.create_search_task(
            SearchTaskRequest(
                keyword="scope",
                provider="justoneapi",
                provider_options=JustOneApiOptions(time_filter="ONE_WEEK"),
            )
        )

        self.assertNotEqual(all_time["task_id"], one_week["task_id"])


if __name__ == "__main__":
    unittest.main()
