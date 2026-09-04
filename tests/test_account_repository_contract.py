import ast
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
from enum import Enum
from pathlib import Path
from types import SimpleNamespace

temp_root = Path(sys.argv[1]).resolve()

class AccountStatus(str, Enum):
    ACTIVE = "active"
    CAPTCHA = "captcha"
    COOLING_DOWN = "cooling_down"
    INVALID = "invalid"

sdb = types.ModuleType("service.service_db")
sdb.AccountStatus = AccountStatus
sys.modules["service.service_db"] = sdb
'''


class AccountRepositoryContractTests(unittest.TestCase):
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

    def test_adapter_preserves_identity_and_dynamic_delegation(self):
        self._run_case(
            r'''
            from service.repositories.accounts import AccountRepository, AccountStatus as ExportedStatus

            assert ExportedStatus is AccountStatus
            assert AccountRepository.AccountStatus is AccountStatus
            repository = AccountRepository()
            methods = (
                "get_active_accounts", "update_account", "get_account",
                "get_proxy_profile", "list_accounts", "add_account",
                "delete_account", "list_candidate_accounts",
                "upsert_candidate_account", "delete_candidate_account",
            )
            events = []
            markers = {}
            for name in methods:
                marker = object()
                markers[name] = marker
                async def delegated(*args, _name=name, _marker=marker, **kwargs):
                    events.append((_name, args, kwargs))
                    return _marker
                setattr(sdb, name, delegated)

            async def run():
                for index, name in enumerate(methods):
                    result = await getattr(repository, name)(index, flag=name)
                    assert result is markers[name]
                failure = RuntimeError("delegated failure")
                async def fail(*args, **kwargs):
                    raise failure
                sdb.get_account = fail
                try:
                    await repository.get_account(99)
                except RuntimeError as exc:
                    assert exc is failure
                else:
                    raise AssertionError("exception must propagate")
            asyncio.run(run())
            assert events == [(name, (index,), {"flag": name}) for index, name in enumerate(methods)]
            print('RESULT=' + json.dumps({"ok": True}))
            '''
        )

    def test_pool_uses_only_injected_repository(self):
        self._run_case(
            r'''
            crawler = types.ModuleType("service.crawler_engine")
            crawler.XHSCrawlerEngine = object
            sys.modules["service.crawler_engine"] = crawler
            from service import account_pool

            for name in (
                "get_active_accounts", "update_account", "get_account",
                "get_proxy_profile", "list_accounts",
            ):
                setattr(sdb, name, lambda *args, _name=name, **kwargs: (_ for _ in ()).throw(AssertionError(_name)))

            events = []
            class Repository:
                async def get_account(self, account_id):
                    events.append(("get_account", account_id))
                    return {"captcha_count": 2}
                async def update_account(self, account_id, **values):
                    events.append(("update_account", account_id, values))
                async def list_accounts(self):
                    return [{
                        "id": 4, "name": "four", "proxy_id": None,
                        "status": "active", "captcha_count": 2,
                        "last_checked": "then", "created_at": "before",
                        "cookie": "a1=value",
                    }]
                async def get_proxy_profile(self, proxy_id, *, include_secret):
                    events.append(("get_proxy", proxy_id, include_secret))
                    return None

            class Engine:
                account_id = 4
                status = "ready"
                message = "ok"

            async def run():
                repository = Repository()
                pool = account_pool.AccountPool(Engine(), repository)
                await pool.adopt_engine(4, Engine())
                engine = pool._pool[4]
                await pool.mark_captcha(engine)
                result = await pool.list_accounts_with_status()
                assert result[0]["id"] == 4
                assert result[0]["cookie_preview"] == "has a1"
                assert pool._repository is repository
            asyncio.run(run())
            assert events[0] == ("get_account", 4)
            assert events[1][0:2] == ("update_account", 4)
            assert events[1][2]["status"] is AccountStatus.CAPTCHA
            assert events[2] == ("get_proxy", None, False)
            print('RESULT=' + json.dumps({"ok": True}))
            '''
        )

    def test_service_and_qr_use_injected_repository(self):
        self._run_case(
            r'''
            pool_module = types.ModuleType("service.account_pool")
            pool_module.AccountPool = object
            sys.modules["service.account_pool"] = pool_module
            crawler = types.ModuleType("service.crawler_engine")
            crawler.XHSCrawlerEngine = object
            sys.modules["service.crawler_engine"] = crawler
            manager = types.ModuleType("service.task_manager")
            manager.TaskManager = object
            sys.modules["service.task_manager"] = manager
            from service.services import account_service

            for name in ("get_proxy_profile", "add_account", "update_account", "delete_account"):
                setattr(sdb, name, lambda *args, _name=name, **kwargs: (_ for _ in ()).throw(AssertionError(_name)))

            events = []
            class Repository:
                async def get_proxy_profile(self, proxy_id, *, include_secret):
                    events.append(("proxy", proxy_id, include_secret))
                    return {"id": proxy_id, "status": "active"}
                async def add_account(self, *args):
                    events.append(("add", args))
                    return 17
                async def update_account(self, account_id, **values):
                    events.append(("update", account_id, values))

            class Engine:
                async def start(self): pass
                async def get_qrcode_for_web(self):
                    return {"qrcode": "image", "session_before": "old"}
                async def stop(self): pass

            class Pool:
                async def add_account(self, *args):
                    events.append(("pool.add", args))
                    return True

            async def run():
                repository = Repository()
                account_service.XHSCrawlerEngine = lambda **kwargs: Engine()
                qr = account_service.QrSessionService(str(temp_root), repository=repository)
                qr_result = await qr.start(" name ", 8)
                assert qr_result["qrcode"] == "image"
                service = account_service.AccountService(Pool(), qr, repository=repository)
                req = SimpleNamespace(name=" account ", cookie=" cookie ", proxy_id=8)
                result = await service.add_account(req)
                assert result["account_id"] == 17
                assert service._repository is repository
                assert qr._repository is repository
                await qr.close_all()
            asyncio.run(run())
            assert events == [
                ("proxy", 8, True),
                ("proxy", 8, False),
                ("add", ("account", "cookie", 8)),
                ("pool.add", (17, "account", "cookie", 8)),
                ("update", 17, {"status": "active"}),
            ]
            print('RESULT=' + json.dumps({"ok": True}))
            '''
        )

    def test_candidate_operations_and_default_constructors_remain_compatible(self):
        self._run_case(
            r'''
            pool_module = types.ModuleType("service.account_pool")
            pool_module.AccountPool = object
            sys.modules["service.account_pool"] = pool_module
            crawler = types.ModuleType("service.crawler_engine")
            crawler.XHSCrawlerEngine = object
            sys.modules["service.crawler_engine"] = crawler
            manager = types.ModuleType("service.task_manager")
            manager.TaskManager = object
            sys.modules["service.task_manager"] = manager
            from service.services.account_service import AccountService, QrSessionService
            from service.repositories.accounts import AccountRepository

            events = []
            async def list_candidates():
                events.append(("list",))
                return [{"id": 1}]
            async def upsert(item):
                events.append(("upsert", item))
                return len(events)
            async def delete(candidate_id):
                events.append(("delete", candidate_id))
            sdb.list_candidate_accounts = list_candidates
            sdb.upsert_candidate_account = upsert
            sdb.delete_candidate_account = delete

            class Item:
                def __init__(self, value): self.value = value
                def model_dump(self): return dict(self.value)

            async def run():
                qr = QrSessionService(str(temp_root))
                service = AccountService(object(), qr)
                assert isinstance(qr._repository, AccountRepository)
                assert isinstance(service._repository, AccountRepository)
                assert await service.list_candidate_accounts() == [{"id": 1}]
                request = SimpleNamespace(accounts=[
                    Item({"source": "s", "phone": " 1 ", "user_id": ""}),
                    Item({"source": "s", "phone": "", "user_id": " u "}),
                ])
                result = await service.save_candidate_accounts(request)
                assert result["count"] == 2
                await service.delete_candidate_account(9)
            asyncio.run(run())
            assert events == [
                ("list",),
                ("upsert", {"source": "s", "phone": "1", "user_id": ""}),
                ("upsert", {"source": "s", "phone": "", "user_id": "u"}),
                ("delete", 9),
            ]
            print('RESULT=' + json.dumps({"ok": True}))
            '''
        )

    def test_static_boundary_and_shared_production_wiring(self):
        self._run_case(
            r'''
            import ast

            for relative in ("service/account_pool.py", "service/services/account_service.py"):
                source = (Path.cwd() / relative).read_text(encoding="utf-8-sig")
                tree = ast.parse(source)
                assert "sdb." not in source
                assert not any(
                    isinstance(node, ast.ImportFrom)
                    and node.module in {"service_db", "service.service_db"}
                    for node in ast.walk(tree)
                )

            events = []
            def module(name, **attributes):
                value = types.ModuleType(name)
                for key, item in attributes.items(): setattr(value, key, item)
                sys.modules[name] = value
                return value

            class Recorder:
                def __init__(self, *args, **kwargs):
                    self.args = args
                    self.kwargs = kwargs
                    events.append((type(self).__name__, self))

            names = (
                "XHSCrawlerEngine", "AccountPool", "JustOneApiTaskExecutor",
                "LocalTaskExecutor", "ExecutorRegistry", "JustOneApiClient",
                "AccountService", "QrSessionService", "ExportService",
                "NoteQueryService", "ProxyService", "TaskService", "TaskManager",
            )
            classes = {name: type(name, (Recorder,), {}) for name in names}
            module("service.account_pool", AccountPool=classes["AccountPool"])
            module("service.crawler_engine", XHSCrawlerEngine=classes["XHSCrawlerEngine"])
            module("service.executors.justoneapi", JustOneApiTaskExecutor=classes["JustOneApiTaskExecutor"])
            module("service.executors.local", LocalTaskExecutor=classes["LocalTaskExecutor"])
            module("service.executors.registry", ExecutorRegistry=classes["ExecutorRegistry"])
            module("service.providers.justoneapi.client", JustOneApiClient=classes["JustOneApiClient"])
            module("service.services.account_service", AccountService=classes["AccountService"], QrSessionService=classes["QrSessionService"])
            module("service.services.export_service", ExportService=classes["ExportService"])
            module("service.services.note_service", NoteQueryService=classes["NoteQueryService"])
            module("service.services.proxy_service", ProxyService=classes["ProxyService"])
            module("service.services.task_service", TaskService=classes["TaskService"])
            module("service.task_manager", TaskManager=classes["TaskManager"])

            config = types.ModuleType("config")
            settings_module = types.ModuleType("config.settings")
            settings_module.settings = SimpleNamespace(
                justoneapi_token="", justoneapi_base_url="https://example.test",
                justoneapi_timeout_sec=1, justoneapi_max_retries=0,
                justoneapi_retry_base_sec=0, local_crawler_enabled=False,
                justoneapi_enabled=False, justoneapi_max_requests_per_task=1,
            )
            sys.modules["config"] = config
            sys.modules["config.settings"] = settings_module

            import service.dependencies as dependencies
            repository = dependencies.account_repository
            assert dependencies.pool.kwargs["repository"] is repository
            assert dependencies.qr_sessions.kwargs["repository"] is repository
            assert dependencies.account_service.kwargs["repository"] is repository
            assert dependencies.get_pool() is dependencies.pool
            assert sum(1 for name, _ in events if name == "AccountPool") == 1
            print('RESULT=' + json.dumps({"ok": True}))
            '''
        )


if __name__ == "__main__":
    unittest.main()
