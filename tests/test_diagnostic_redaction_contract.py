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
from pathlib import Path

temp_root = Path(sys.argv[1]).resolve()
'''


class DiagnosticRedactionContractTests(unittest.TestCase):
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
        result = json.loads(result_lines[0][7:])
        self.assertEqual(result, {"leaked": False, "redacted": True})

    def test_proxy_failure_redacts_returned_and_persisted_diagnostics(self):
        self._run_case(
            r'''
            sdb = types.ModuleType("service.service_db")
            sys.modules["service.service_db"] = sdb

            from service.services import proxy_service

            secrets = (
                "token-secret",
                "auth-secret",
                "cookie-secret",
                "userinfo-secret",
                "password-secret",
            )
            diagnostic = (
                "request failed token=token-secret\n"
                "Authorization: Bearer auth-secret\n"
                "Cookie: sid=cookie-secret\n"
                "proxy=http://user:userinfo-secret@example.test:8080 "
                "password=password-secret"
            )
            profile = {
                "id": 7,
                "server": "proxy.test:8080",
                "proxy_type": "http",
                "username": "proxy-user",
                "password": "proxy-password",
                "status": "active",
            }
            updates = []
            client_args = []

            async def get_profile(proxy_id, *, include_secret=False):
                assert (proxy_id, include_secret) == (7, True)
                return dict(profile)

            async def update_profile(proxy_id, **values):
                updates.append((proxy_id, values))

            sdb.get_proxy_profile = get_profile
            sdb.update_proxy_profile = update_profile

            class FixedNow:
                def isoformat(self):
                    return "2026-09-04T10:00:00"

            class FixedDatetime:
                @staticmethod
                def now():
                    return FixedNow()

            proxy_service.datetime = FixedDatetime

            class FailingClient:
                def __init__(self, **kwargs):
                    client_args.append(kwargs)

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    return False

                async def get(self, url):
                    assert url == proxy_service.ProxyService._CHECK_URL
                    raise RuntimeError(diagnostic)

            async def run():
                proxy_service.httpx.AsyncClient = FailingClient
                service = proxy_service.ProxyService()
                result = await service.check_proxy(7)
                assert set(result) == {"ok", "observed_ip", "message", "error"}
                assert result["ok"] is False
                assert result["observed_ip"] == ""
                assert result["message"] == "Proxy check failed."
                assert result["error"].startswith("RuntimeError: request failed")
                assert client_args == [{
                    "proxy": "http://proxy-user:proxy-password@proxy.test:8080",
                    "timeout": 20,
                }]
                assert updates == [(7, {
                    "last_checked": "2026-09-04T10:00:00",
                    "last_error": result["error"][:500],
                })]
                persisted = updates[0][1]["last_error"]

                class Response:
                    def raise_for_status(self):
                        return None

                    def json(self):
                        return {"ip": "203.0.113.9"}

                class SuccessClient:
                    def __init__(self, **kwargs):
                        assert kwargs == client_args[0]

                    async def __aenter__(self):
                        return self

                    async def __aexit__(self, *args):
                        return False

                    async def get(self, url):
                        return Response()

                updates.clear()
                proxy_service.httpx.AsyncClient = SuccessClient
                success = await service.check_proxy(7)
                assert success == {
                    "ok": True,
                    "observed_ip": "203.0.113.9",
                    "message": "Proxy check passed.",
                    "error": "",
                }
                assert updates == [(7, {
                    "last_checked": "2026-09-04T10:00:00",
                    "last_error": "",
                })]

                rendered = result["error"] + "\n" + persisted
                leaked = any(secret in rendered for secret in secrets)
                redacted = "<redacted>" in result["error"] and "<redacted>" in persisted
                print('RESULT=' + json.dumps({"leaked": leaked, "redacted": redacted}))

            asyncio.run(run())
            '''
        )

    def test_qr_pong_failure_redacts_only_diagnostic_and_preserves_cookie(self):
        self._run_case(
            r'''
            def install_module(name, **attributes):
                module = types.ModuleType(name)
                for key, value in attributes.items():
                    setattr(module, key, value)
                sys.modules[name] = module
                return module

            playwright = install_module("playwright")
            playwright.__path__ = []
            install_module(
                "playwright.async_api",
                BrowserContext=object,
                Page=object,
                async_playwright=lambda: None,
            )
            install_module("aiosqlite", connect=lambda *args, **kwargs: None)

            database = install_module("database")
            database.__path__ = []
            async def create_tables(*args, **kwargs):
                raise AssertionError("real database is forbidden")
            install_module("database.db_session", create_tables=create_tables)

            media_platform = install_module("media_platform")
            media_platform.__path__ = []
            xhs_package = install_module("media_platform.xhs")
            xhs_package.__path__ = []
            class XHSError(Exception):
                pass
            install_module(
                "media_platform.xhs.client",
                XiaoHongShuClient=object,
                XHSAuthError=XHSError,
                XHSCaptchaError=type("XHSCaptchaError", (XHSError,), {}),
                XHSPermissionError=type("XHSPermissionError", (XHSError,), {}),
                XHSRateLimitError=type("XHSRateLimitError", (XHSError,), {}),
            )
            install_module("media_platform.xhs.field", SearchSortType=object)
            install_module(
                "media_platform.xhs.help",
                get_search_id=lambda: "",
                parse_creator_info_from_url=lambda value: None,
                parse_note_info_from_note_url=lambda value: None,
            )
            install_module("media_platform.xhs.login", XiaoHongShuLogin=object)

            store = install_module("store")
            store.__path__ = []
            install_module("store.xhs")
            install_module(
                "tools.crawler_util",
                convert_browser_context_cookies=lambda value: None,
                convert_cookies=lambda cookies: ("", {"web_session": "new-session"}),
            )

            from service import crawler_engine

            diagnostic_secret = "exception-token-secret"
            legacy_cookie = "web_session=legacy-cookie;a1=legacy-a1"

            class Page:
                def __init__(self, events):
                    self.events = events

                async def is_visible(self, selector, timeout):
                    self.events.append(("visible", selector, timeout))
                    return True

            class Context:
                def __init__(self, events):
                    self.events = events

                async def cookies(self):
                    self.events.append(("cookies",))
                    return [{"name": "web_session", "value": "new-session"}]

            class Client:
                def __init__(self, events, failure):
                    self.events = events
                    self.failure = failure
                    self.headers = {"Cookie": legacy_cookie}

                async def pong(self):
                    self.events.append(("pong",))
                    if self.failure:
                        raise RuntimeError(f"token={diagnostic_secret}")
                    return True

            class Logger:
                def __init__(self, events):
                    self.events = events

                def warning(self, message):
                    self.events.append(("log", message))

            def make_engine(failure):
                events = []
                engine = object.__new__(crawler_engine.XHSCrawlerEngine)
                engine._page = Page(events)
                engine._browser_context = Context(events)
                engine._xhs_client = Client(events, failure)
                engine.status = "waiting_qrcode"
                engine.message = "Waiting for QR login..."
                async def refresh():
                    events.append(("refresh",))
                engine._refresh_client = refresh
                crawler_engine.logger = Logger(events)
                return engine, events

            async def run():
                engine, events = make_engine(True)
                result = await engine.check_qrcode_login_done("old-session")
                assert set(result) == {"done", "verified", "cookie", "error"}
                assert result["done"] is True
                assert result["verified"] is False
                assert result["cookie"] == legacy_cookie
                assert result["error"].startswith("post-login verification failed: ")
                assert engine.status == "waiting_qrcode"
                assert [event[0] for event in events] == [
                    "visible", "cookies", "refresh", "pong", "log"
                ]
                logged = events[-1][1]

                success_engine, success_events = make_engine(False)
                success = await success_engine.check_qrcode_login_done("old-session")
                assert success == {
                    "done": True,
                    "verified": True,
                    "cookie": legacy_cookie,
                }
                assert success_engine.status == "ready"
                assert success_engine.message == "QR login succeeded"
                assert [event[0] for event in success_events] == [
                    "visible", "cookies", "refresh", "pong"
                ]

                leaked = diagnostic_secret in result["error"] or diagnostic_secret in logged
                redacted = "<redacted>" in result["error"] and "<redacted>" in logged
                print('RESULT=' + json.dumps({"leaked": leaked, "redacted": redacted}))

            asyncio.run(run())
            '''
        )


if __name__ == "__main__":
    unittest.main()
