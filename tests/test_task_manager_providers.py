import asyncio
import os
import tempfile
import unittest

from service import service_db as db
from service.executors.base import (
    ExecutionContext,
    ProviderReadiness,
    TaskExecutor,
)
from service.executors.registry import ExecutorRegistry
from service.task_manager import TaskManager


class FakeExecutor(TaskExecutor):
    def __init__(
        self,
        provider: str,
        readiness: ProviderReadiness,
        *,
        block: bool = False,
        result=None,
    ):
        self.provider = provider
        self._readiness = readiness
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.block = block
        self.result = result or {"notes_count": 1, "comments_count": 2}
        self.calls = 0

    async def readiness(self) -> ProviderReadiness:
        return self._readiness

    async def execute(self, task, params, context: ExecutionContext):
        self.calls += 1
        self.started.set()
        if self.block:
            await self.release.wait()
        return dict(self.result)


async def wait_for_status(task_id: int, expected: str, timeout: float = 2.0):
    async def poll():
        while True:
            task = await db.get_task(task_id)
            if task and task["status"] == expected:
                return task
            await asyncio.sleep(0.01)

    return await asyncio.wait_for(poll(), timeout=timeout)


class TaskManagerProviderTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._original_path = db.SERVICE_DB_PATH
        self._temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        db.SERVICE_DB_PATH = os.path.join(self._temp_dir.name, "service.db")
        await db.init_service_db()
        self._managers = []

    async def asyncTearDown(self):
        for manager in reversed(self._managers):
            await manager.stop()
        db.SERVICE_DB_PATH = self._original_path
        self._temp_dir.cleanup()

    def make_manager(self, *executors: TaskExecutor) -> TaskManager:
        manager = TaskManager(ExecutorRegistry(executors))
        self._managers.append(manager)
        return manager

    async def test_api_task_runs_without_a_ready_local_account(self):
        local = FakeExecutor(
            "local",
            ProviderReadiness(enabled=True, ready=False, reason="no_ready_account"),
        )
        api = FakeExecutor(
            "justoneapi",
            ProviderReadiness(enabled=True, ready=True),
        )
        manager = self.make_manager(local, api)
        await manager.start()

        task_id = await manager.submit(
            db.TaskType.SEARCH.value,
            {"keyword": "api-only"},
            provider=db.TaskProvider.JUSTONEAPI,
        )

        task = await wait_for_status(task_id, db.TaskStatus.COMPLETED.value)
        self.assertEqual(api.calls, 1)
        self.assertEqual(task["notes_count"], 1)
        self.assertEqual(task["comments_count"], 2)

    async def test_provider_workers_do_not_block_each_other(self):
        local = FakeExecutor(
            "local",
            ProviderReadiness(enabled=True, ready=True),
            block=True,
        )
        api = FakeExecutor(
            "justoneapi",
            ProviderReadiness(enabled=True, ready=True),
        )
        manager = self.make_manager(local, api)
        await manager.start()

        local_task_id = await manager.submit(
            db.TaskType.SEARCH.value,
            {"keyword": "slow-local"},
        )
        await asyncio.wait_for(local.started.wait(), timeout=1.0)
        api_task_id = await manager.submit(
            db.TaskType.SEARCH.value,
            {"keyword": "fast-api"},
            provider=db.TaskProvider.JUSTONEAPI,
        )

        await wait_for_status(api_task_id, db.TaskStatus.COMPLETED.value)
        self.assertEqual((await db.get_task(local_task_id))["status"], "running")

        local.release.set()
        await wait_for_status(local_task_id, db.TaskStatus.COMPLETED.value)

    async def test_concurrent_deduplicated_submits_only_enqueue_once(self):
        api = FakeExecutor(
            "justoneapi",
            ProviderReadiness(enabled=True, ready=True),
        )
        manager = self.make_manager(api)
        params = {"keyword": "same"}

        task_ids = await asyncio.gather(
            *(
                manager.submit(
                    db.TaskType.SEARCH.value,
                    params,
                    provider=db.TaskProvider.JUSTONEAPI,
                )
                for _ in range(10)
            )
        )

        self.assertEqual(len(set(task_ids)), 1)
        self.assertEqual(manager.queue_size(db.TaskProvider.JUSTONEAPI), 1)

        await manager.start()
        await wait_for_status(task_ids[0], db.TaskStatus.COMPLETED.value)
        await asyncio.sleep(0.05)
        self.assertEqual(api.calls, 1)
        self.assertEqual(manager.queue_size(db.TaskProvider.JUSTONEAPI), 0)

    async def test_budget_exhaustion_requires_manual_resubmission(self):
        api = FakeExecutor(
            "justoneapi",
            ProviderReadiness(enabled=True, ready=True),
            result={
                "notes_count": 1,
                "comments_count": 0,
                "budget_exhausted": True,
            },
        )
        manager = self.make_manager(api)
        await manager.start()

        task_id = await manager.submit(
            db.TaskType.SEARCH.value,
            {"keyword": "budget"},
            provider=db.TaskProvider.JUSTONEAPI,
        )
        task = await wait_for_status(task_id, db.TaskStatus.PAUSED.value)

        self.assertEqual(task["manual_resume_required"], 1)
        self.assertEqual(
            await db.list_paused_task_ids(provider=db.TaskProvider.JUSTONEAPI),
            [],
        )


if __name__ == "__main__":
    unittest.main()
