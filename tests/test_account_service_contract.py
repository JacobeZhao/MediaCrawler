import atexit
import json
import os
import site
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

CHILD_PRELUDE = r'''
import asyncio
import json
import sys
import types
from types import SimpleNamespace

sdb = types.ModuleType("service.service_db")
sys.modules["service.service_db"] = sdb

account_pool = types.ModuleType("service.account_pool")
account_pool.AccountPool = type("AccountPool", (), {})
sys.modules["service.account_pool"] = account_pool

crawler_engine = types.ModuleType("service.crawler_engine")
crawler_engine.XHSCrawlerEngine = type("XHSCrawlerEngine", (), {})
sys.modules["service.crawler_engine"] = crawler_engine

task_manager = types.ModuleType("service.task_manager")
task_manager.TaskManager = type("TaskManager", (), {})
sys.modules["service.task_manager"] = task_manager

from fastapi import HTTPException
from service.services.account_service import AccountService
'''


class AccountServiceContractTests(unittest.TestCase):
    def _run_case(self, body):
        parent_modules = set(sys.modules)
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            env_file = temp_root / "empty.env"
            env_file.write_bytes(b"")
            pycache = temp_root / "pycache"
            pycache.mkdir()
            import_paths = [str(ROOT)]
            import_paths.extend(path for path in sys.path if path)
            import_paths.extend(site.getsitepackages())
            env = {
                "PYTHONPATH": os.pathsep.join(dict.fromkeys(import_paths)),
                "PYTHONPYCACHEPREFIX": str(pycache),
                "PYTHONDONTWRITEBYTECODE": "1",
                "XHS_ENV_FILE": str(env_file),
            }
            for name in ("SystemRoot", "WINDIR", "TEMP", "TMP"):
                if value := os.environ.get(name):
                    env[name] = value
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-c",
                    CHILD_PRELUDE + "\n" + textwrap.dedent(body),
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
                shell=False,
            )
        self.assertEqual(set(sys.modules), parent_modules)
        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
        )
        result_lines = [
            line for line in completed.stdout.splitlines() if line.startswith("RESULT=")
        ]
        self.assertEqual(len(result_lines), 1, msg=completed.stdout)
        self.assertEqual(json.loads(result_lines[0][7:]), {"ok": True})

    def test_add_success_and_failed_startup_preserve_order_and_rollback(self):
        self._run_case(
            r'''
            async def run():
                events = []
                next_id = iter((41, 42))

                async def get_proxy(proxy_id, *, include_secret=False):
                    events.append(("proxy", proxy_id, include_secret))
                    return {"id": proxy_id, "status": "active"}

                async def add(name, cookie, proxy_id):
                    account_id = next(next_id)
                    events.append(("db.add", account_id, name, cookie, proxy_id))
                    return account_id

                async def update(account_id, **values):
                    events.append(("db.update", account_id, values))

                async def delete(account_id):
                    events.append(("db.delete", account_id))

                sdb.get_proxy_profile = get_proxy
                sdb.add_account = add
                sdb.update_account = update
                sdb.delete_account = delete

                class Pool:
                    async def add_account(self, account_id, name, cookie, proxy_id):
                        events.append(("pool.add", account_id, name, cookie, proxy_id))
                        return cookie != "bad-cookie"

                class Manager:
                    async def requeue_paused_tasks_now(self):
                        events.append(("wake",))

                service = AccountService(Pool(), SimpleNamespace(), Manager())
                good = SimpleNamespace(
                    name=" account ", cookie=" good-cookie ", proxy_id=7
                )
                result = await service.add_account(good)
                assert result == {"account_id": 41, "message": "Account  account  added."}
                assert "good-cookie" not in repr(result)
                assert events == [
                    ("proxy", 7, False),
                    ("db.add", 41, "account", "good-cookie", 7),
                    ("pool.add", 41, "account", "good-cookie", 7),
                    ("db.update", 41, {"status": "active"}),
                    ("wake",),
                ]

                events.clear()
                bad = SimpleNamespace(name="bad", cookie="bad-cookie", proxy_id=None)
                try:
                    await service.add_account(bad)
                    raise AssertionError("failed startup must raise")
                except HTTPException as exc:
                    assert (exc.status_code, exc.detail) == (
                        400,
                        "Cookie is invalid or account startup failed.",
                    )
                assert events == [
                    ("db.add", 42, "bad", "bad-cookie", None),
                    ("pool.add", 42, "bad", "bad-cookie", None),
                    ("db.delete", 42),
                ]

            asyncio.run(run())
            print('RESULT=' + json.dumps({"ok": True}))
            '''
        )

    def test_cookie_replacement_restores_exact_old_identity_on_false_start(self):
        self._run_case(
            r'''
            async def run():
                events = []
                account = {
                    "id": 8, "name": "saved", "cookie": "old-cookie", "proxy_id": 3
                }

                async def get_account(account_id):
                    events.append(("db.get", account_id))
                    return dict(account)

                async def update(account_id, **values):
                    events.append(("db.update", account_id, values))

                sdb.get_account = get_account
                sdb.update_account = update

                class Pool:
                    async def remove_account(self, account_id):
                        events.append(("pool.remove", account_id))

                    async def add_account(self, account_id, name, cookie, proxy_id):
                        events.append(("pool.add", account_id, name, cookie, proxy_id))
                        return cookie != "bad-new"

                class Manager:
                    async def requeue_paused_tasks_now(self):
                        events.append(("wake",))

                service = AccountService(Pool(), SimpleNamespace(), Manager())
                result = await service.update_account_cookie(
                    8, SimpleNamespace(cookie=" new-cookie ")
                )
                assert result == {"message": "Cookie updated."}
                assert events == [
                    ("db.get", 8),
                    ("pool.remove", 8),
                    ("pool.add", 8, "saved", "new-cookie", 3),
                    ("db.update", 8, {"cookie": "new-cookie", "status": "active"}),
                    ("wake",),
                ]

                events.clear()
                try:
                    await service.update_account_cookie(
                        8, SimpleNamespace(cookie="bad-new")
                    )
                    raise AssertionError("invalid replacement must raise")
                except HTTPException as exc:
                    assert (exc.status_code, exc.detail) == (400, "New cookie is invalid.")
                assert events == [
                    ("db.get", 8),
                    ("pool.remove", 8),
                    ("pool.add", 8, "saved", "bad-new", 3),
                    ("pool.add", 8, "saved", "old-cookie", 3),
                ]

            asyncio.run(run())
            print('RESULT=' + json.dumps({"ok": True}))
            '''
        )

    def test_proxy_replacement_preserves_restart_false_and_success_order(self):
        self._run_case(
            r'''
            async def run():
                events = []
                account = {
                    "id": 9, "name": "saved", "cookie": "old-cookie", "proxy_id": 2
                }

                async def get_account(account_id):
                    events.append(("db.get", account_id))
                    return dict(account)

                async def get_proxy(proxy_id, *, include_secret=False):
                    events.append(("proxy", proxy_id, include_secret))
                    return {"id": proxy_id, "status": "active"}

                async def update(account_id, **values):
                    events.append(("db.update", account_id, values))

                sdb.get_account = get_account
                sdb.get_proxy_profile = get_proxy
                sdb.update_account = update

                class Pool:
                    async def remove_account(self, account_id):
                        events.append(("pool.remove", account_id))

                    async def add_account(self, account_id, name, cookie, proxy_id):
                        events.append(("pool.add", account_id, name, cookie, proxy_id))
                        return True

                service = AccountService(Pool(), SimpleNamespace(), None)
                result = await service.update_account_proxy(
                    9, SimpleNamespace(proxy_id=5, restart=False)
                )
                assert result == {"message": "Account proxy updated."}
                assert events == [
                    ("db.get", 9),
                    ("proxy", 5, False),
                    ("db.update", 9, {"proxy_id": 5}),
                ]

                events.clear()
                result = await service.update_account_proxy(
                    9, SimpleNamespace(proxy_id=6, restart=True)
                )
                assert result == {"message": "Account proxy updated."}
                assert events == [
                    ("db.get", 9),
                    ("proxy", 6, False),
                    ("pool.remove", 9),
                    ("pool.add", 9, "saved", "old-cookie", 6),
                    ("db.update", 9, {"proxy_id": 6}),
                    ("db.update", 9, {"status": "active"}),
                ]

            asyncio.run(run())
            print('RESULT=' + json.dumps({"ok": True}))
            '''
        )

    def test_proxy_restart_failure_attempts_only_defined_restoration(self):
        self._run_case(
            r'''
            async def run():
                events = []
                account = {
                    "id": 10, "name": "saved", "cookie": "old-cookie", "proxy_id": 2
                }

                async def get_account(account_id):
                    events.append(("db.get", account_id))
                    return dict(account)

                async def get_proxy(proxy_id, *, include_secret=False):
                    events.append(("proxy", proxy_id, include_secret))
                    return {"id": proxy_id, "status": "active"}

                async def unexpected_update(*args, **kwargs):
                    raise AssertionError("failed restart must not mutate DB")

                sdb.get_account = get_account
                sdb.get_proxy_profile = get_proxy
                sdb.update_account = unexpected_update

                class Pool:
                    async def remove_account(self, account_id):
                        events.append(("pool.remove", account_id))

                    async def add_account(self, account_id, name, cookie, proxy_id):
                        events.append(("pool.add", account_id, name, cookie, proxy_id))
                        return proxy_id == 2

                service = AccountService(Pool(), SimpleNamespace(), None)
                try:
                    await service.update_account_proxy(
                        10, SimpleNamespace(proxy_id=7, restart=True)
                    )
                    raise AssertionError("failed restart must raise")
                except HTTPException as exc:
                    assert (exc.status_code, exc.detail) == (
                        400,
                        "Account failed to restart with the selected proxy.",
                    )
                assert events == [
                    ("db.get", 10),
                    ("proxy", 7, False),
                    ("pool.remove", 10),
                    ("pool.add", 10, "saved", "old-cookie", 7),
                    ("pool.add", 10, "saved", "old-cookie", 2),
                ]

            asyncio.run(run())
            print('RESULT=' + json.dumps({"ok": True}))
            '''
        )

    def test_verified_qr_transfers_engine_without_returning_cookie(self):
        self._run_case(
            r'''
            async def run():
                events = []

                class Engine:
                    async def check_qrcode_login_done(self, session_before):
                        events.append(("engine.check", session_before))
                        return {
                            "done": True,
                            "verified": True,
                            "cookie": "web_session=legacy-cookie",
                        }

                engine = Engine()

                class Sessions:
                    async def get(self, session_id):
                        events.append(("session.get", session_id))
                        return {
                            "engine": engine,
                            "name": "qr-account",
                            "proxy_id": 4,
                            "session_before": "before",
                        }

                    def forget(self, session_id):
                        events.append(("session.forget", session_id))

                class Pool:
                    async def adopt_engine(self, account_id, adopted):
                        assert adopted is engine
                        events.append(("pool.adopt", account_id))

                class Manager:
                    async def requeue_paused_tasks_now(self):
                        events.append(("wake",))

                async def add(name, cookie, proxy_id):
                    events.append(("db.add", name, cookie, proxy_id))
                    return 71

                async def update(account_id, **values):
                    events.append(("db.update", account_id, values))

                sdb.add_account = add
                sdb.update_account = update
                service = AccountService(Pool(), Sessions(), Manager())
                result = await service.poll_qrcode("session-id")
                assert result == {
                    "status": "success",
                    "account_id": 71,
                    "name": "qr-account",
                    "message": "Account qr-account added by QR login.",
                }
                assert "cookie" not in result
                assert events == [
                    ("session.get", "session-id"),
                    ("engine.check", "before"),
                    ("db.add", "qr-account", "web_session=legacy-cookie", 4),
                    ("pool.adopt", 71),
                    ("db.update", 71, {"status": "active"}),
                    ("session.forget", "session-id"),
                    ("wake",),
                ]

            asyncio.run(run())
            print('RESULT=' + json.dumps({"ok": True}))
            '''
        )

    def test_pending_and_unverified_qr_do_not_transfer_session_ownership(self):
        self._run_case(
            r'''
            async def run():
                class Engine:
                    def __init__(self, result):
                        self.result = result

                    async def check_qrcode_login_done(self, session_before):
                        assert session_before == "before"
                        return dict(self.result)

                class Sessions:
                    def __init__(self, result):
                        self.engine = Engine(result)
                        self.forgotten = []

                    async def get(self, session_id):
                        return {
                            "engine": self.engine,
                            "name": "qr-account",
                            "proxy_id": None,
                            "session_before": "before",
                        }

                    def forget(self, session_id):
                        self.forgotten.append(session_id)

                class ForbiddenPool:
                    async def adopt_engine(self, *args):
                        raise AssertionError("pending QR must not adopt")

                async def forbidden(*args, **kwargs):
                    raise AssertionError("pending QR must not persist or wake")

                sdb.add_account = forbidden
                sdb.update_account = forbidden

                cases = (
                    ({"done": False, "error": "still waiting"}, {"status": "pending", "message": "still waiting"}),
                    ({"done": False}, {"status": "pending", "message": "Waiting for QR login confirmation."}),
                )
                for engine_result, expected in cases:
                    sessions = Sessions(engine_result)
                    service = AccountService(ForbiddenPool(), sessions, SimpleNamespace(requeue_paused_tasks_now=forbidden))
                    assert await service.poll_qrcode("session-id") == expected
                    assert sessions.forgotten == []

                sessions = Sessions({
                    "done": True,
                    "verified": False,
                    "cookie": "web_session=legacy-cookie",
                    "error": "verification failed",
                })
                service = AccountService(ForbiddenPool(), sessions, SimpleNamespace(requeue_paused_tasks_now=forbidden))
                try:
                    await service.poll_qrcode("session-id")
                    raise AssertionError("unverified QR must raise")
                except HTTPException as exc:
                    assert (exc.status_code, exc.detail) == (400, "verification failed")
                assert sessions.forgotten == []

            asyncio.run(run())
            print('RESULT=' + json.dumps({"ok": True}))
            '''
        )


if __name__ == "__main__":
    unittest.main()
