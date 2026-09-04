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
import ast
import asyncio
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace

root = Path(sys.argv[1]).resolve()
temp_root = Path(sys.argv[2]).resolve()

sdb = types.ModuleType("service.service_db")
sys.modules["service.service_db"] = sdb
'''


class ProxyRepositoryContractTests(unittest.TestCase):
    maxDiff = None

    def _run_case(self, body: str):
        parent_modules = set(sys.modules)
        before_cwd = os.getcwd()
        before_env = dict(os.environ)
        with tempfile.TemporaryDirectory(prefix="proxy-contract-") as directory:
            temp_root = Path(directory).resolve()
            for name in ("home", "profile", "temp", "pycache"):
                (temp_root / name).mkdir()
            (temp_root / "empty.env").touch()
            import_paths = [str(ROOT)]
            import_paths.extend(path for path in sys.path if path)
            import_paths.extend(site.getsitepackages())
            env = {
                "PYTHONPATH": os.pathsep.join(dict.fromkeys(import_paths)),
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONIOENCODING": "utf-8",
                "PYTHONPYCACHEPREFIX": str(temp_root / "pycache"),
                "XHS_ENV_FILE": str(temp_root / "empty.env"),
                "HOME": str(temp_root / "home"),
                "USERPROFILE": str(temp_root / "profile"),
                "TEMP": str(temp_root / "temp"),
                "TMP": str(temp_root / "temp"),
            }
            for name in ("SystemRoot", "WINDIR", "COMSPEC", "SYSTEMDRIVE"):
                if value := os.environ.get(name):
                    env[name] = value
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-c",
                    CHILD_PRELUDE + "\n" + textwrap.dedent(body),
                    str(ROOT),
                    str(temp_root),
                ],
                cwd=temp_root,
                env=env,
                shell=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=15,
                check=False,
            )
        self.assertEqual(os.getcwd(), before_cwd)
        self.assertEqual(dict(os.environ), before_env)
        self.assertEqual(set(sys.modules), parent_modules)
        self.assertEqual(
            completed.returncode,
            0,
            f"child failed\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
        )
        records = [
            line.removeprefix("RESULT=")
            for line in completed.stdout.splitlines()
            if line.startswith("RESULT=")
        ]
        self.assertEqual(len(records), 1, completed.stdout)
        self.assertEqual(json.loads(records[0]), {"ok": True})

    def test_adapter_dynamic_delegation_arguments_returns_and_exceptions(self):
        self._run_case(
            r'''
            from service.repositories.proxies import ProxyRepository

            repository = ProxyRepository()
            methods = (
                "list_proxy_profiles", "get_proxy_profile", "add_proxy_profile",
                "update_proxy_profile", "delete_proxy_profile",
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
                failure = RuntimeError("same failure")
                async def fail(*args, **kwargs):
                    raise failure
                sdb.get_proxy_profile = fail
                try:
                    await repository.get_proxy_profile(9)
                except RuntimeError as exc:
                    assert exc is failure
                else:
                    raise AssertionError("exception identity was not preserved")

            asyncio.run(run())
            assert events == [
                (name, (index,), {"flag": name})
                for index, name in enumerate(methods)
            ]
            print("RESULT=" + json.dumps({"ok": True}))
            '''
        )

    def test_default_and_explicit_falsy_repository_injection_preserve_identity(self):
        self._run_case(
            r'''
            from service.repositories.proxies import ProxyRepository
            from service.services.proxy_service import ProxyService

            default = ProxyService()
            assert isinstance(default._repository, ProxyRepository)

            class FalsyRepository:
                def __bool__(self):
                    return False

            supplied = FalsyRepository()
            service = ProxyService(repository=supplied)
            assert service._repository is supplied
            print("RESULT=" + json.dumps({"ok": True}))
            '''
        )

    def test_crud_preserves_flags_ordering_normalization_payloads_and_error_matrix(self):
        self._run_case(
            r'''
            from fastapi import HTTPException
            from service.schemas.proxies import ProxyProfileRequest, ProxyProfileUpdateRequest
            from service.services.proxy_service import ProxyService

            class Repository:
                def __init__(self):
                    self.events = []
                    self.profiles = {
                        3: {
                            "id": 3, "name": "old", "proxy_type": "socks5",
                            "server": "socks5://old.test:1080", "username": "",
                            "password": "", "has_password": False, "status": "active",
                        }
                    }
                    self.fail_add = False
                    self.fail_update = False
                    self.fail_delete = False

                async def list_proxy_profiles(self, *, include_secret):
                    self.events.append(("list", include_secret))
                    return [dict(self.profiles[key]) for key in sorted(self.profiles, reverse=True)]

                async def add_proxy_profile(self, data):
                    self.events.append(("add", dict(data)))
                    if self.fail_add:
                        raise ValueError("duplicate")
                    self.profiles[7] = {"id": 7, **data, "has_password": bool(data["password"])}
                    return 7

                async def get_proxy_profile(self, proxy_id, *, include_secret):
                    self.events.append(("get", proxy_id, include_secret))
                    profile = self.profiles.get(proxy_id)
                    return dict(profile) if profile else None

                async def update_proxy_profile(self, proxy_id, **values):
                    self.events.append(("update", proxy_id, dict(values)))
                    if self.fail_update:
                        raise ValueError("duplicate update")
                    self.profiles[proxy_id].update(values)

                async def delete_proxy_profile(self, proxy_id):
                    self.events.append(("delete", proxy_id))
                    if self.fail_delete:
                        raise ValueError("bound")

            async def expect_http(status, detail, operation):
                try:
                    await operation()
                except HTTPException as exc:
                    assert (exc.status_code, exc.detail) == (status, detail)
                else:
                    raise AssertionError(f"expected HTTP {status}")

            async def run():
                repository = Repository()
                service = ProxyService(repository)
                listed = await service.list_proxies()
                assert [item["id"] for item in listed] == [3]
                assert repository.events[-1] == ("list", False)
                assert "password" not in listed[0]

                created = await service.create_proxy(ProxyProfileRequest(
                    name=" seven ", proxy_type="https", server=" proxy.test:8443 ",
                    username="user", password="secret", status="active",
                ))
                add = next(event for event in repository.events if event[0] == "add")
                assert add[1]["server"] == "https://proxy.test:8443"
                assert created["proxy_id"] == 7
                assert created["message"] == "Proxy profile created."
                assert "password" not in created["proxy"]
                assert created["proxy"]["has_auth"] is True

                await expect_http(400, "Proxy server must not include path, query, or fragment.", lambda: service.create_proxy(
                    ProxyProfileRequest(name="bad", server="http://proxy.test/path")
                ))
                repository.fail_add = True
                await expect_http(409, "duplicate", lambda: service.create_proxy(
                    ProxyProfileRequest(name="dup", server="proxy.test:80")
                ))
                repository.fail_add = False

                await expect_http(404, "Proxy profile not found.", lambda: service.update_proxy(
                    99, ProxyProfileUpdateRequest(status="inactive")
                ))
                await expect_http(400, "Proxy server must not include path, query, or fragment.", lambda: service.update_proxy(
                    3, ProxyProfileUpdateRequest(server="socks5://new.test/path")
                ))
                updated = await service.update_proxy(
                    3, ProxyProfileUpdateRequest(server=" new.test:1090 ", status="inactive")
                )
                update = [event for event in repository.events if event[0] == "update"][-1]
                assert update == ("update", 3, {"server": "socks5://new.test:1090", "status": "inactive"})
                assert updated["message"] == "Proxy profile updated."
                repository.fail_update = True
                await expect_http(409, "duplicate update", lambda: service.update_proxy(
                    3, ProxyProfileUpdateRequest(name="taken")
                ))

                assert await service.delete_proxy(3) == {"message": "Proxy profile deleted."}
                repository.fail_delete = True
                await expect_http(409, "bound", lambda: service.delete_proxy(3))

            asyncio.run(run())
            print("RESULT=" + json.dumps({"ok": True}))
            '''
        )

    def test_check_preserves_secret_lookup_http_time_redaction_and_truncation(self):
        self._run_case(
            r'''
            from fastapi import HTTPException
            from service.services import proxy_service

            profile = {
                "id": 3, "proxy_type": "http", "server": "proxy.test:8080",
                "username": "user", "password": "p word", "status": "active",
            }

            class Repository:
                def __init__(self):
                    self.updates = []

                async def get_proxy_profile(self, proxy_id, *, include_secret):
                    assert include_secret is True
                    if proxy_id == 1:
                        return None
                    if proxy_id == 2:
                        return {"server": "", "proxy_type": "http"}
                    if proxy_id == 4:
                        return {"server": "ftp://proxy.test", "proxy_type": "http"}
                    return dict(profile)

                async def update_proxy_profile(self, proxy_id, **values):
                    self.updates.append((proxy_id, values))

            class FixedNow:
                def isoformat(self):
                    return "2026-09-04T12:34:56"

            class FixedDatetime:
                @staticmethod
                def now():
                    return FixedNow()

            proxy_service.datetime = FixedDatetime
            client_options = []
            diagnostic = "token=super-secret " + ("x" * 700)

            class FailingClient:
                def __init__(self, **kwargs):
                    client_options.append(kwargs)
                async def __aenter__(self): return self
                async def __aexit__(self, *args): return False
                async def get(self, url):
                    assert url == proxy_service.ProxyService._CHECK_URL
                    raise RuntimeError(diagnostic)

            class Response:
                def raise_for_status(self): return None
                def json(self): return {"ip": "203.0.113.10"}

            class SuccessClient:
                def __init__(self, **kwargs):
                    client_options.append(kwargs)
                async def __aenter__(self): return self
                async def __aexit__(self, *args): return False
                async def get(self, url): return Response()

            async def expect_http(proxy_id, status, detail):
                try:
                    await service.check_proxy(proxy_id)
                except HTTPException as exc:
                    assert (exc.status_code, exc.detail) == (status, detail)
                else:
                    raise AssertionError(f"expected HTTP {status}")

            async def run():
                repository = Repository()
                global service
                service = proxy_service.ProxyService(repository)
                await expect_http(1, 404, "Proxy profile not found.")
                await expect_http(2, 400, "Proxy profile is incomplete.")
                await expect_http(4, 400, "Unsupported proxy type.")

                proxy_service.httpx.AsyncClient = FailingClient
                failed = await service.check_proxy(3)
                assert failed["ok"] is False
                assert failed["observed_ip"] == ""
                assert failed["message"] == "Proxy check failed."
                assert failed["error"].startswith("RuntimeError: token=<redacted>")
                assert "super-secret" not in failed["error"]
                assert len(failed["error"]) > 500
                persisted = repository.updates[-1]
                assert persisted[0] == 3
                assert persisted[1]["last_checked"] == "2026-09-04T12:34:56"
                assert persisted[1]["last_error"] == failed["error"][:500]
                assert len(persisted[1]["last_error"]) == 500

                proxy_service.httpx.AsyncClient = SuccessClient
                succeeded = await service.check_proxy(3)
                assert succeeded == {
                    "ok": True, "observed_ip": "203.0.113.10",
                    "message": "Proxy check passed.", "error": "",
                }
                assert repository.updates[-1][1] == {
                    "last_checked": "2026-09-04T12:34:56", "last_error": "",
                }
                assert client_options == [
                    {"proxy": "http://user:p%20word@proxy.test:8080", "timeout": 20},
                    {"proxy": "http://user:p%20word@proxy.test:8080", "timeout": 20},
                ]

            asyncio.run(run())
            print("RESULT=" + json.dumps({"ok": True}))
            '''
        )

    def test_static_ownership_and_production_composition_share_one_repository(self):
        self._run_case(
            r'''
            proxy_source = (root / "service/services/proxy_service.py").read_text(encoding="utf-8-sig")
            proxy_tree = ast.parse(proxy_source)
            assert "sdb." not in proxy_source
            assert not any(
                isinstance(node, ast.ImportFrom)
                and node.module in {"service_db", "service.service_db"}
                for node in ast.walk(proxy_tree)
            )
            account_source = (root / "service/repositories/accounts.py").read_text(encoding="utf-8-sig")
            assert "async def get_proxy_profile" in account_source

            events = []
            def install(name, **attributes):
                value = types.ModuleType(name)
                value.__dict__.update(attributes)
                sys.modules[name] = value
                return value

            class Recorder:
                def __init__(self, *args, **kwargs):
                    self.args = args
                    self.kwargs = kwargs
                    events.append((type(self).__name__, self))

            names = (
                "AccountPool", "XHSCrawlerEngine", "JustOneApiTaskExecutor",
                "LocalTaskExecutor", "ExecutorRegistry", "JustOneApiClient",
                "AccountRepository", "ProxyRepository", "AccountService",
                "QrSessionService", "ExportService", "NoteQueryService",
                "ProxyService", "TaskService", "TaskManager",
            )
            classes = {name: type(name, (Recorder,), {}) for name in names}
            install("service.account_pool", AccountPool=classes["AccountPool"])
            install("service.crawler_engine", XHSCrawlerEngine=classes["XHSCrawlerEngine"])
            install("service.executors.justoneapi", JustOneApiTaskExecutor=classes["JustOneApiTaskExecutor"])
            install("service.executors.local", LocalTaskExecutor=classes["LocalTaskExecutor"])
            install("service.executors.registry", ExecutorRegistry=classes["ExecutorRegistry"])
            install("service.providers.justoneapi.client", JustOneApiClient=classes["JustOneApiClient"])
            install("service.repositories.accounts", AccountRepository=classes["AccountRepository"])
            install("service.repositories.proxies", ProxyRepository=classes["ProxyRepository"])
            install("service.services.account_service", AccountService=classes["AccountService"], QrSessionService=classes["QrSessionService"])
            install("service.services.export_service", ExportService=classes["ExportService"])
            install("service.services.note_service", NoteQueryService=classes["NoteQueryService"])
            install("service.services.proxy_service", ProxyService=classes["ProxyService"])
            install("service.services.task_service", TaskService=classes["TaskService"])
            install("service.task_manager", TaskManager=classes["TaskManager"])

            config = install("config")
            config.__path__ = []
            install("config.settings", settings=SimpleNamespace(
                justoneapi_token="synthetic", justoneapi_base_url="https://invalid.example.test",
                justoneapi_timeout_sec=1, justoneapi_max_retries=0,
                justoneapi_retry_base_sec=0, local_crawler_enabled=False,
                justoneapi_enabled=False, justoneapi_max_requests_per_task=1,
            ))

            import service.dependencies as dependencies
            proxies = [value for name, value in events if name == "ProxyRepository"]
            assert len(proxies) == 1
            assert dependencies.proxy_repository is proxies[0]
            assert dependencies.proxy_service.kwargs == {"repository": proxies[0]}
            accounts = dependencies.account_repository
            assert dependencies.pool.kwargs["repository"] is accounts
            assert dependencies.qr_sessions.kwargs["repository"] is accounts
            assert dependencies.account_service.kwargs["repository"] is accounts
            print("RESULT=" + json.dumps({"ok": True}))
            '''
        )


if __name__ == "__main__":
    unittest.main()
