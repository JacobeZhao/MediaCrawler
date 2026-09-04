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
import os
import sys
import types
from enum import Enum
from pathlib import Path
from unittest.mock import patch

class AccountStatus(str, Enum):
    ACTIVE = "active"
    CAPTCHA = "captcha"
    COOLING_DOWN = "cooling_down"
    INVALID = "invalid"

sdb = types.ModuleType("service.service_db")
sdb.AccountStatus = AccountStatus
sys.modules["service.service_db"] = sdb

crawler_engine = types.ModuleType("service.crawler_engine")
crawler_engine.XHSCrawlerEngine = type("XHSCrawlerEngine", (), {})
sys.modules["service.crawler_engine"] = crawler_engine

from service import account_pool
from service.account_pool import AccountPool, EngineStatus

temp_root = Path(sys.argv[1]).resolve()
account_pool._PROJECT_ROOT = str(temp_root)
'''


class AccountPoolContractTests(unittest.TestCase):
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
                    str(temp_root),
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

    def test_ready_selection_rotation_and_default_fallback(self):
        self._run_case(
            r'''
            class Engine:
                def __init__(self, account_id, status):
                    self.account_id = account_id
                    self.status = status
                    self.message = ""

            async def run():
                default = Engine(None, "stopped")
                pool = AccountPool(default)
                first = Engine(1, "ready")
                second = Engine(2, "ready")
                blocked = Engine(3, "captcha")
                await pool.adopt_engine(1, first)
                await pool.adopt_engine(2, second)
                await pool.adopt_engine(3, blocked)

                assert await pool.get_healthy_engine() is first
                pool._advance_rotation_index()
                assert await pool.get_healthy_engine() is second
                second.status = "cooling_down"
                assert await pool.get_healthy_engine() is first
                first.status = "captcha"
                default.status = "ready"
                assert await pool.get_healthy_engine() is default
                default.status = "stopped"
                assert await pool.get_healthy_engine() is None

            asyncio.run(run())
            print('RESULT=' + json.dumps({"ok": True}))
            '''
        )

    def test_concurrent_captcha_and_cooldown_updates_are_identity_isolated(self):
        self._run_case(
            r'''
            class Engine:
                def __init__(self, account_id):
                    self.account_id = account_id
                    self.status = "ready"
                    self.message = ""

            async def run():
                updates = []
                arrived = 0
                gate = asyncio.Event()

                async def get_account(account_id):
                    assert account_id == 1
                    return {"captcha_count": 4}

                async def update(account_id, **values):
                    nonlocal arrived
                    updates.append((account_id, values))
                    arrived += 1
                    if arrived == 2:
                        gate.set()
                    await asyncio.wait_for(gate.wait(), timeout=1)

                sdb.get_account = get_account
                sdb.update_account = update
                default = Engine(None)
                first = Engine(1)
                second = Engine(2)
                third = Engine(3)
                pool = AccountPool(default)
                await pool.adopt_engine(1, first)
                await pool.adopt_engine(2, second)
                await pool.adopt_engine(3, third)

                with patch.object(account_pool.time, "monotonic", return_value=100.0):
                    await asyncio.gather(
                        pool.mark_captcha(first),
                        pool.mark_temporarily_unavailable(second, duration=30),
                    )

                assert first.status == "captcha"
                assert second.status == "cooling_down"
                assert third.status == "ready"
                assert default.status == "ready"
                assert set(pool._cool_until) == {id(second)}
                normalized = {
                    (account_id, values["status"].value, values.get("captcha_count"))
                    for account_id, values in updates
                }
                assert normalized == {
                    (1, "captcha", 5),
                    (2, "cooling_down", None),
                }

            asyncio.run(run())
            print('RESULT=' + json.dumps({"ok": True}))
            '''
        )

    def test_cooldown_expiry_requires_successful_health_probe(self):
        self._run_case(
            r'''
            class Engine:
                def __init__(self, account_id, probe):
                    self.account_id = account_id
                    self.status = "ready"
                    self.message = ""
                    self._probe = probe

                async def probe_login(self):
                    return dict(self._probe)

            async def run():
                updates = []

                async def update(account_id, **values):
                    updates.append((account_id, values["status"].value))

                sdb.update_account = update
                default = Engine(None, {"ok": False, "has_login_cookie": False, "error": None})
                default.status = "stopped"
                recovered = Engine(1, {"ok": True, "has_login_cookie": True, "error": None})
                captcha = Engine(2, {"ok": False, "has_login_cookie": True, "error": "captcha appeared"})
                captcha.status = "captcha"
                pool = AccountPool(default)
                await pool.adopt_engine(1, recovered)
                await pool.adopt_engine(2, captcha)
                pool._failure_counts[id(recovered)] = 2

                with patch.object(account_pool.time, "monotonic", return_value=100.0):
                    await pool.mark_temporarily_unavailable(recovered, duration=10)
                with patch.object(account_pool.time, "monotonic", return_value=111.0):
                    assert await pool.get_healthy_engine() is None

                assert recovered.status == "cooling_down"
                assert recovered.message == "cooldown finished; health check pending"
                assert id(recovered) not in pool._cool_until
                results = await pool.health_check_all()
                assert recovered.status == "ready"
                assert captcha.status == "captcha"
                assert id(recovered) not in pool._failure_counts
                assert results == [
                    {
                        "account_id": 1,
                        "ok": True,
                        "has_login_cookie": True,
                        "status": "active",
                        "error": None,
                        "error_type": "none",
                        "next_action": "no_action",
                    },
                    {
                        "account_id": 2,
                        "ok": False,
                        "has_login_cookie": True,
                        "status": "captcha",
                        "error": "captcha appeared",
                        "error_type": "captcha",
                        "next_action": "manual_verify_or_wait",
                    },
                ]
                assert updates == [
                    (1, "cooling_down"),
                    (1, "active"),
                    (2, "captcha"),
                ]

            asyncio.run(run())
            print('RESULT=' + json.dumps({"ok": True}))
            '''
        )

    def test_concurrent_adopt_and_remove_preserve_engine_identity(self):
        self._run_case(
            r'''
            class Engine:
                def __init__(self):
                    self.account_id = None
                    self.status = "ready"
                    self.message = ""
                    self.stop_calls = 0

                async def stop(self):
                    self.stop_calls += 1

            async def run():
                default = Engine()
                default.status = "stopped"
                first = Engine()
                second = Engine()
                pool = AccountPool(default)
                await asyncio.gather(
                    pool.adopt_engine(11, first),
                    pool.adopt_engine(12, second),
                )
                assert (first.account_id, second.account_id) == (11, 12)
                assert pool.pool_size() == 2
                assert pool.ready_count() == 2

                await asyncio.gather(
                    pool.remove_account(11),
                    pool.remove_account(999),
                )
                assert first.stop_calls == 1
                assert second.stop_calls == 0
                assert pool.pool_size() == 1
                assert pool.ready_count() == 1
                assert await pool.get_healthy_engine() is second

            asyncio.run(run())
            print('RESULT=' + json.dumps({"ok": True}))
            '''
        )

    def test_start_failures_stop_and_never_register_engines(self):
        self._run_case(
            r'''
            class Engine:
                instances = []

                def __init__(self, account_id, user_data_dir, proxy_config):
                    self.account_id = account_id
                    self.user_data_dir = user_data_dir
                    self.proxy_config = proxy_config
                    self.status = "stopped"
                    self.message = "invalid cookie"
                    self.stop_calls = 0
                    Engine.instances.append(self)

                async def start(self):
                    if self.account_id == 1:
                        raise RuntimeError("startup failed")

                async def set_cookie(self, cookie):
                    return False

                async def probe_login(self):
                    return {
                        "ok": False,
                        "has_login_cookie": False,
                        "error": "invalid cookie",
                    }

                async def stop(self):
                    self.stop_calls += 1

            async def run():
                updates = []

                async def get_proxy(proxy_id, *, include_secret=False):
                    if proxy_id == 404:
                        return None
                    if proxy_id == 405:
                        return {"id": proxy_id, "status": "inactive", "server": "proxy.test:8080"}
                    return {"id": proxy_id, "status": "active", "server": "proxy.test:8080"}

                async def update(account_id, **values):
                    updates.append((account_id, values["status"].value))

                sdb.get_proxy_profile = get_proxy
                sdb.update_account = update
                account_pool.XHSCrawlerEngine = Engine
                default = Engine(0, str(temp_root / "default"), None)
                Engine.instances.clear()
                pool = AccountPool(default)

                assert not await pool.add_account(1, "one", "cookie", 10)
                assert not await pool.add_account(2, "two", "cookie", 10)
                constructed = len(Engine.instances)
                assert not await pool.add_account(3, "three", "cookie", 404)
                assert not await pool.add_account(4, "four", "cookie", 405)
                assert len(Engine.instances) == constructed == 2
                assert [engine.stop_calls for engine in Engine.instances] == [1, 1]
                assert pool.pool_size() == 0
                assert pool.ready_count() == 0
                assert updates == [(2, "invalid")]
                assert all(Path(engine.user_data_dir).is_relative_to(temp_root) for engine in Engine.instances)

            asyncio.run(run())
            print('RESULT=' + json.dumps({"ok": True}))
            '''
        )

    def test_account_projection_preserves_keys_and_hides_credentials(self):
        self._run_case(
            r'''
            class Engine:
                account_id = 21
                status = "crawling"
                message = "working"

            async def run():
                async def list_accounts():
                    return [{
                        "id": 21,
                        "name": "saved",
                        "proxy_id": 8,
                        "status": "active",
                        "captcha_count": 2,
                        "last_checked": "checked",
                        "created_at": "created",
                        "cookie": "web_session=session-secret; a1=a1-secret; id_token=id-secret; xsecappid=x-secret; other=other-secret",
                    }]

                async def get_proxy(proxy_id, *, include_secret=False):
                    assert (proxy_id, include_secret) == (8, False)
                    return {
                        "id": 8,
                        "name": "proxy",
                        "server": "proxy.test:8080",
                        "proxy_type": "http",
                        "username": "proxy-user",
                        "has_password": True,
                        "status": "active",
                    }

                sdb.list_accounts = list_accounts
                sdb.get_proxy_profile = get_proxy
                default = Engine()
                default.status = "stopped"
                pool = AccountPool(default)
                engine = Engine()
                await pool.adopt_engine(21, engine)
                result = await pool.list_accounts_with_status()
                assert result == [{
                    "id": 21,
                    "name": "saved",
                    "proxy_id": 8,
                    "proxy_name": "proxy",
                    "proxy_server": "http://proxy-user:***@proxy.test:8080",
                    "proxy_status": "active",
                    "status": "active",
                    "runtime_status": "crawling",
                    "captcha_count": 2,
                    "last_checked": "checked",
                    "created_at": "created",
                    "cookie_preview": "has web_session, a1, id_token, xsecappid",
                    "message": "working",
                }]
                rendered = repr(result)
                for secret in ("session-secret", "a1-secret", "id-secret", "x-secret", "other-secret"):
                    assert secret not in rendered

            asyncio.run(run())
            print('RESULT=' + json.dumps({"ok": True}))
            '''
        )


if __name__ == "__main__":
    unittest.main()
