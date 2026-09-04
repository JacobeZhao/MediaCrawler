import atexit
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_TARGETS = {"service.dependencies", "service.main", "service.app"}

# These import-time effects characterize the current runtime; TD-003 must update them.

CHILD_SCRIPT = textwrap.dedent(
    r"""
    import asyncio
    import importlib
    import json
    import os
    import sys
    import types
    from pathlib import Path
    from types import SimpleNamespace

    scenario = sys.argv[1]
    root = Path(sys.argv[2]).resolve()
    temp_root = Path(sys.argv[3]).resolve()
    os.chdir(temp_root)
    sys.path.insert(0, str(root))


    def module(name, **attributes):
        value = types.ModuleType(name)
        value.__dict__.update(attributes)
        sys.modules[name] = value
        return value


    def service_package():
        package = module("service")
        package.__path__ = [str(root / "service")]
        return package


    def install_dependency_stubs():
        service_package()
        settings = SimpleNamespace(
            justoneapi_token="synthetic-token",
            justoneapi_base_url="https://invalid.example.test",
            justoneapi_timeout_sec=17,
            justoneapi_max_retries=3,
            justoneapi_retry_base_sec=0.25,
            local_crawler_enabled=True,
            justoneapi_enabled=False,
            justoneapi_max_requests_per_task=29,
        )
        config = module("config")
        config.__path__ = []
        module("config.settings", settings=settings)

        constructions = {}

        def fake_class(name):
            class Fake:
                def __init__(self, *args, **kwargs):
                    self.args = args
                    self.kwargs = kwargs
                    constructions.setdefault(name, []).append(self)

            Fake.__name__ = name
            return Fake

        leaves = {
            "service.account_pool": ["AccountPool"],
            "service.crawler_engine": ["XHSCrawlerEngine"],
            "service.executors.justoneapi": ["JustOneApiTaskExecutor"],
            "service.executors.local": ["LocalTaskExecutor"],
            "service.executors.registry": ["ExecutorRegistry"],
            "service.providers.justoneapi.client": ["JustOneApiClient"],
            "service.repositories.accounts": ["AccountRepository"],
            "service.repositories.proxies": ["ProxyRepository"],
            "service.services.account_service": ["AccountService", "QrSessionService"],
            "service.services.export_service": ["ExportService"],
            "service.services.note_service": ["NoteQueryService"],
            "service.services.proxy_service": ["ProxyService"],
            "service.services.task_service": ["TaskService"],
            "service.task_manager": ["TaskManager"],
        }
        for name in (
            "service.executors",
            "service.providers",
            "service.providers.justoneapi",
            "service.repositories",
            "service.services",
        ):
            package = module(name)
            package.__path__ = []
        for name, classes in leaves.items():
            module(name, **{item: fake_class(item) for item in classes})
        return config, settings, constructions


    def dependency_graph():
        config, settings, made = install_dependency_stubs()
        target = importlib.import_module("service.dependencies")
        expected = {
            "AccountRepository",
            "ProxyRepository",
            "XHSCrawlerEngine",
            "AccountPool",
            "JustOneApiClient",
            "LocalTaskExecutor",
            "JustOneApiTaskExecutor",
            "ExecutorRegistry",
            "TaskManager",
            "QrSessionService",
            "AccountService",
            "TaskService",
            "NoteQueryService",
            "ExportService",
            "ProxyService",
        }
        counts = {name: len(made.get(name, [])) for name in sorted(expected)}
        pool = target.pool
        client = target.justoneapi_client
        registry = made["ExecutorRegistry"][0]
        local_executor, remote_executor = registry.args[0]
        manager = target.task_manager
        qr = target.qr_sessions
        account = target.account_service
        identities = {
            "pool_engine": pool.kwargs["default_engine"] is target.engine,
            "pool_repository": pool.kwargs["repository"] is target.account_repository,
            "local_pool": local_executor.args[0] is pool,
            "remote_client": remote_executor.args[0] is client,
            "manager_registry": manager.args[0] is registry,
            "qr_repository": qr.kwargs["repository"] is target.account_repository,
            "account_pool": account.args[0] is pool,
            "account_qr": account.args[1] is qr,
            "account_manager": account.args[2] is manager,
            "account_repository": account.kwargs["repository"] is target.account_repository,
            "proxy_repository": target.proxy_service.kwargs["repository"] is target.proxy_repository,
            "task_manager": target.task_service.args[0] is manager,
        }
        accessors = {
            name: getattr(target, "get_" + name)() is getattr(target, name)
            for name in (
                "engine",
                "pool",
                "task_manager",
                "account_service",
                "task_service",
                "note_query_service",
                "export_service",
                "proxy_service",
            )
        }
        options = {
            "client": [
                client.args[0] == settings.justoneapi_token,
                client.kwargs["base_url"] == settings.justoneapi_base_url,
                client.kwargs["timeout_sec"] == settings.justoneapi_timeout_sec,
                client.kwargs["max_retries"] == settings.justoneapi_max_retries,
                client.kwargs["retry_base_sec"] == settings.justoneapi_retry_base_sec,
            ],
            "local_enabled": local_executor.kwargs["enabled"] is True,
            "remote_enabled": remote_executor.kwargs["enabled"] is False,
            "remote_limit": remote_executor.kwargs["max_requests_per_task"] == 29,
            "image_consumers": (
                target.note_query_service.args[0] == target.IMAGE_DIR
                and target.export_service.args[0] == target.IMAGE_DIR
            ),
        }
        return {
            "counts": counts,
            "identities": identities,
            "accessors": accessors,
            "options": options,
            "projection": [
                config.SAVE_DATA_OPTION,
                config.PLATFORM,
                config.ENABLE_GET_COMMENTS,
            ],
            "paths_under_root": all(
                str(Path(path).resolve()).startswith(str(root))
                for path in (target.ROOT_DIR, target.STATIC_DIR, target.IMAGE_DIR)
            ),
        }


    EVENTS = []
    FAILURES = {}
    ORIGINAL_MAKEDIRS = os.makedirs


    class Component:
        def __init__(self, name):
            self.name = name

        def _call(self, action):
            label = self.name + "." + action
            EVENTS.append(label)
            failure = FAILURES.get(label)
            if failure is not None:
                raise failure

        async def start(self):
            self._call("start")

        async def stop(self):
            self._call("stop")

        async def aclose(self):
            self._call("aclose")

        async def close_all(self):
            self._call("close_all")


    class RuntimeLock:
        instances = []

        def __init__(self):
            EVENTS.append("lock.new")
            RuntimeLock.instances.append(self)
            failure = FAILURES.get("lock.new")
            if failure is not None:
                raise failure

        def acquire(self):
            EVENTS.append("lock.acquire")
            failure = FAILURES.get("lock.acquire")
            if failure is not None:
                raise failure

        def release(self):
            EVENTS.append("lock.release")
            failure = FAILURES.get("lock.release")
            if failure is not None:
                raise failure


    class FileResponse:
        def __init__(self, path):
            self.path = path


    class HTMLResponse:
        def __init__(self, content):
            self.content = content


    class StaticFiles:
        def __init__(self, directory):
            self.directory = directory


    class CORSMiddleware:
        pass


    class FastAPI:
        instances = []

        def __init__(self, **kwargs):
            EVENTS.append("fastapi.new")
            self.title = kwargs.get("title")
            self.version = kwargs.get("version")
            self.lifespan = kwargs.get("lifespan")
            self.state = SimpleNamespace()
            self.middleware = []
            self.routers = []
            self.mounts = []
            self.endpoints = {}
            FastAPI.instances.append(self)

        def add_middleware(self, middleware, **kwargs):
            self.middleware.append((middleware, kwargs))

        def include_router(self, router):
            self.routers.append(router)

        def mount(self, path, app, name=None):
            self.mounts.append((path, app, name))

        def get(self, path, **kwargs):
            def decorate(function):
                self.endpoints[path] = (function, kwargs)
                return function

            return decorate


    def install_main_stubs():
        service_package()
        image_dir = temp_root / "runtime" / "images"
        static_dir = temp_root / "runtime" / "static"
        static_dir.mkdir(parents=True, exist_ok=True)

        def load_root_env():
            EVENTS.append("env.load")

        module("service.runtime_env", load_root_env=load_root_env)
        module("fastapi", FastAPI=FastAPI)
        fastapi_middleware = module("fastapi.middleware")
        fastapi_middleware.__path__ = []
        module("fastapi.middleware.cors", CORSMiddleware=CORSMiddleware)
        module("fastapi.responses", FileResponse=FileResponse, HTMLResponse=HTMLResponse)
        module("fastapi.staticfiles", StaticFiles=StaticFiles)

        settings = SimpleNamespace(local_crawler_enabled=False, sqlite_db_path=str(temp_root / "runtime" / "service.db"))
        config = module("config")
        config.__path__ = []
        module("config.settings", settings=settings)

        async def create_tables(kind):
            EVENTS.append("tables.create:" + kind)
            failure = FAILURES.get("tables.create")
            if failure is not None:
                raise failure

        async def dispose_engines():
            EVENTS.append("engines.dispose")
            failure = FAILURES.get("engines.dispose")
            if failure is not None:
                raise failure

        database = module("database")
        database.__path__ = []
        module("database.db_session", create_tables=create_tables, dispose_engines=dispose_engines)

        async def init_service_db():
            EVENTS.append("service_db.init")
            failure = FAILURES.get("service_db.init")
            if failure is not None:
                raise failure

        module("service.service_db", init_service_db=init_service_db)
        module("service.runtime_lock", RuntimeLock=RuntimeLock)

        dependencies = module(
            "service.dependencies",
            IMAGE_DIR=str(image_dir),
            STATIC_DIR=str(static_dir),
            engine=Component("engine"),
            justoneapi_client=Component("client"),
            pool=Component("pool"),
            qr_sessions=Component("qr"),
            task_manager=Component("task"),
        )
        routes = module("service.routes")
        routes.__path__ = []
        for name in ("accounts", "export", "login", "notes", "proxies", "status", "tasks"):
            child = module("service.routes." + name, router=name)
            setattr(routes, name, child)
        return settings, dependencies, image_dir, static_dir


    def import_main():
        settings, dependencies, image_dir, static_dir = install_main_stubs()
        target = importlib.import_module("service.main")
        original = target.os.makedirs

        def recorded_makedirs(path, *args, **kwargs):
            resolved = str(Path(path).resolve())
            EVENTS.append("fs.makedirs:" + resolved)
            failure = FAILURES.get("fs.makedirs")
            if failure is not None:
                raise failure
            return original(path, *args, **kwargs)

        target.os.makedirs = recorded_makedirs
        return target, settings, dependencies, image_dir, static_dir


    async def exercise_lifespan(target, settings, enabled=False, failures=None, body_failure=None):
        EVENTS.clear()
        FAILURES.clear()
        RuntimeLock.instances.clear()
        settings.local_crawler_enabled = enabled
        FAILURES.update(failures or {})
        app = SimpleNamespace(state=SimpleNamespace())
        caught = None
        try:
            async with target.lifespan(app):
                EVENTS.append("body")
                if body_failure is not None:
                    raise body_failure
        except BaseException as exc:
            caught = {"type": type(exc).__name__, "message": str(exc)}
        lock = RuntimeLock.instances[-1] if RuntimeLock.instances else None
        return {
            "events": list(EVENTS),
            "exception": caught,
            "state_has_lock": hasattr(app.state, "runtime_lock"),
            "state_lock_identity": getattr(app.state, "runtime_lock", None) is lock,
        }


    def app_shape():
        target, settings, dependencies, image_dir, static_dir = import_main()
        index_path = static_dir / "index.html"
        index_path.write_text("synthetic frontend", encoding="utf-8")
        facade = importlib.import_module("service.app")
        app = facade.app
        found = asyncio.run(app.endpoints["/"][0]())
        index_path.unlink()
        missing = asyncio.run(app.endpoints["/"][0]())
        middleware, middleware_options = app.middleware[0]
        return {
            "app_count": len(FastAPI.instances),
            "facade_identity": app is FastAPI.instances[0],
            "title": app.title,
            "version": app.version,
            "lifespan_identity": app.lifespan is target.lifespan,
            "middleware": middleware is CORSMiddleware,
            "cors": middleware_options,
            "routers": app.routers,
            "mounts": [
                [path, mounted.directory, name]
                for path, mounted, name in app.mounts
            ],
            "root_found": [type(found).__name__, str(Path(found.path).resolve())],
            "root_missing": [type(missing).__name__, missing.content],
            "image_created": image_dir.is_dir(),
            "import_events": list(EVENTS),
            "paths": [str(image_dir.resolve()), str(static_dir.resolve())],
        }


    def lifecycle_scenario(kind):
        target, settings, dependencies, image_dir, static_dir = import_main()
        EVENTS.clear()
        if kind == "disabled":
            return asyncio.run(exercise_lifespan(target, settings, enabled=False))
        if kind == "enabled":
            return asyncio.run(exercise_lifespan(target, settings, enabled=True))
        if kind == "normal":
            return asyncio.run(exercise_lifespan(target, settings, enabled=True))
        raise AssertionError(kind)


    def startup_failures():
        target, settings, dependencies, image_dir, static_dir = import_main()
        cases = [
            ("lock.new", False),
            ("lock.acquire", False),
            ("service_db.init", False),
            ("fs.makedirs", False),
            ("tables.create", False),
            ("task.start", False),
            ("engine.start", True),
            ("pool.start", True),
            ("task.start", True),
        ]
        result = {}
        for label, enabled in cases:
            result[label + (":enabled" if enabled else ":disabled")] = asyncio.run(
                exercise_lifespan(
                    target,
                    settings,
                    enabled=enabled,
                    failures={label: RuntimeError("failed:" + label)},
                )
            )
        return result


    class HardFailure(BaseException):
        pass


    def cleanup_failures():
        target, settings, dependencies, image_dir, static_dir = import_main()
        cleanup = [
            "task.stop",
            "client.aclose",
            "qr.close_all",
            "pool.stop",
            "engine.stop",
            "engines.dispose",
            "lock.release",
        ]
        singles = {}
        for label in cleanup:
            singles[label] = asyncio.run(
                exercise_lifespan(
                    target,
                    settings,
                    failures={label: HardFailure("hard:" + label)},
                )
            )
        multiple = asyncio.run(
            exercise_lifespan(
                target,
                settings,
                failures={
                    "task.stop": RuntimeError("first-cleanup"),
                    "qr.close_all": HardFailure("later-cleanup"),
                },
            )
        )
        body_only = asyncio.run(
            exercise_lifespan(
                target, settings, body_failure=ValueError("body-error")
            )
        )
        body_and_cleanup = asyncio.run(
            exercise_lifespan(
                target,
                settings,
                failures={"client.aclose": RuntimeError("cleanup-wins")},
                body_failure=ValueError("body-error"),
            )
        )
        startup_and_cleanup = asyncio.run(
            exercise_lifespan(
                target,
                settings,
                failures={
                    "service_db.init": ValueError("startup-error"),
                    "pool.stop": RuntimeError("cleanup-wins-startup"),
                },
            )
        )
        return {
            "singles": singles,
            "multiple": multiple,
            "body_only": body_only,
            "body_and_cleanup": body_and_cleanup,
            "startup_and_cleanup": startup_and_cleanup,
        }


    def isolation_audit():
        before = set(sys.modules)
        shape = app_shape()
        after = set(sys.modules)
        forbidden = [
            name
            for name in ("sqlalchemy", "aiosqlite", "playwright")
            if name in after and name not in before
        ]
        env_paths = {
            name: str(Path(os.environ[name]).resolve())
            for name in (
                "XHS_ENV_FILE",
                "PYTHONPYCACHEPREFIX",
                "HOME",
                "USERPROFILE",
                "TEMP",
                "TMP",
            )
        }
        touched = shape["paths"] + [
            event.split(":", 1)[1]
            for event in shape["import_events"]
            if event.startswith("fs.makedirs:")
        ]
        return {
            "cwd": str(Path.cwd().resolve()),
            "temp_root": str(temp_root),
            "env_paths": env_paths,
            "touched": touched,
            "forbidden_imports": forbidden,
            "network_modules": [name for name in ("socket", "urllib.request", "http.client") if name in after and name not in before],
            "events": shape["import_events"],
        }


    handlers = {
        "dependencies": dependency_graph,
        "app": app_shape,
        "disabled": lambda: lifecycle_scenario("disabled"),
        "enabled": lambda: lifecycle_scenario("enabled"),
        "normal": lambda: lifecycle_scenario("normal"),
        "startup_failures": startup_failures,
        "cleanup_failures": cleanup_failures,
        "isolation": isolation_audit,
    }
    result = handlers[scenario]()
    print("RESULT=" + json.dumps(result, sort_keys=True))
    """
)


def _minimal_child_env(temp_root: Path) -> dict[str, str]:
    env = {
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
        if name in os.environ:
            env[name] = os.environ[name]
    return env


class RuntimeCompositionContractTests(unittest.TestCase):
    maxDiff = None

    def _run_child(self, scenario: str) -> dict:
        before_cwd = os.getcwd()
        before_env = dict(os.environ)
        before_modules = set(sys.modules)
        with tempfile.TemporaryDirectory(prefix="runtime-contract-") as directory:
            temp_root = Path(directory).resolve()
            for name in ("home", "profile", "temp", "pycache"):
                (temp_root / name).mkdir()
            (temp_root / "empty.env").touch()
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-c",
                    CHILD_SCRIPT,
                    scenario,
                    str(ROOT),
                    str(temp_root),
                ],
                cwd=temp_root,
                env=_minimal_child_env(temp_root),
                shell=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=20,
                check=False,
            )
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
            self.assertEqual(records.__len__(), 1, completed.stdout)
            result = json.loads(records[0])
        self.assertEqual(os.getcwd(), before_cwd)
        self.assertEqual(dict(os.environ), before_env)
        self.assertEqual(set(sys.modules), before_modules)
        return result

    def test_dependency_graph_construction_sharing_accessors_and_projection(self):
        result = self._run_child("dependencies")
        self.assertEqual(set(result["counts"].values()), {1})
        self.assertTrue(all(result["identities"].values()))
        self.assertEqual(len(result["accessors"]), 8)
        self.assertTrue(all(result["accessors"].values()))
        self.assertTrue(all(result["options"]["client"]))
        self.assertTrue(result["options"]["local_enabled"])
        self.assertTrue(result["options"]["remote_enabled"])
        self.assertTrue(result["options"]["remote_limit"])
        self.assertTrue(result["options"]["image_consumers"])
        self.assertEqual(result["projection"], ["sqlite", "xhs", True])
        self.assertTrue(result["paths_under_root"])

    def test_application_facade_shape_routes_mounts_roots_and_import_events(self):
        result = self._run_child("app")
        self.assertEqual(result["app_count"], 1)
        self.assertTrue(result["facade_identity"])
        self.assertEqual(result["title"], "XHS Crawler Service")
        self.assertEqual(result["version"], "1.0.0")
        self.assertTrue(result["lifespan_identity"])
        self.assertTrue(result["middleware"])
        self.assertEqual(
            result["cors"],
            {"allow_origins": ["*"], "allow_methods": ["*"], "allow_headers": ["*"]},
        )
        self.assertEqual(
            result["routers"],
            ["status", "login", "accounts", "proxies", "tasks", "notes", "export"],
        )
        self.assertEqual(
            [[mount[0], mount[2]] for mount in result["mounts"]],
            [["/images", "note-images"], ["/static", "static"]],
        )
        self.assertEqual(
            [str(Path(mount[1]).resolve()) for mount in result["mounts"]],
            [str(Path(path).resolve()) for path in result["paths"]],
        )
        self.assertEqual(result["root_found"][0], "FileResponse")
        self.assertTrue(result["root_found"][1].endswith("runtime\\static\\index.html") or result["root_found"][1].endswith("runtime/static/index.html"))
        self.assertEqual(result["root_missing"], ["HTMLResponse", "<h1>Frontend not found</h1>"])
        self.assertTrue(result["image_created"])
        self.assertEqual(result["import_events"][0:2], ["env.load", "fastapi.new"])
        self.assertEqual(len([event for event in result["import_events"] if event.startswith("fs.makedirs:")]), 1)

    def test_disabled_startup_order_omits_local_starts(self):
        result = self._run_child("disabled")
        self.assertIsNone(result["exception"])
        self.assertEqual(
            result["events"][:6],
            ["lock.new", "lock.acquire", "service_db.init", result["events"][3], "tables.create:sqlite", "task.start"],
        )
        self.assertTrue(result["events"][3].startswith("fs.makedirs:"))
        self.assertNotIn("engine.start", result["events"])
        self.assertNotIn("pool.start", result["events"])
        self.assertEqual(result["events"][6], "body")

    def test_enabled_startup_order_through_body_entry(self):
        result = self._run_child("enabled")
        self.assertIsNone(result["exception"])
        self.assertEqual(
            [event for event in result["events"] if not event.startswith("fs.makedirs:")][:8],
            [
                "lock.new",
                "lock.acquire",
                "service_db.init",
                "tables.create:sqlite",
                "engine.start",
                "pool.start",
                "task.start",
                "body",
            ],
        )

    def test_normal_teardown_order_and_runtime_lock_identity(self):
        result = self._run_child("normal")
        self.assertIsNone(result["exception"])
        self.assertTrue(result["state_has_lock"])
        self.assertTrue(result["state_lock_identity"])
        self.assertEqual(
            result["events"][-7:],
            [
                "task.stop",
                "client.aclose",
                "qr.close_all",
                "pool.stop",
                "engine.stop",
                "engines.dispose",
                "lock.release",
            ],
        )

    def test_pre_yield_failure_matrix_and_cleanup_boundary(self):
        result = self._run_child("startup_failures")
        cleanup = ["task.stop", "client.aclose", "qr.close_all", "pool.stop", "engine.stop", "engines.dispose", "lock.release"]
        for name, observation in result.items():
            with self.subTest(case=name):
                label = name.split(":", 1)[0]
                self.assertEqual(observation["exception"]["message"], "failed:" + label)
                self.assertNotIn("body", observation["events"])
                if label in {"lock.new", "lock.acquire"}:
                    self.assertTrue(all(event not in observation["events"] for event in cleanup))
                    self.assertFalse(observation["state_has_lock"])
                else:
                    self.assertEqual(observation["events"][-7:], cleanup)
                    self.assertTrue(observation["state_lock_identity"])

    def test_cleanup_continuation_first_error_and_error_precedence(self):
        result = self._run_child("cleanup_failures")
        cleanup = ["task.stop", "client.aclose", "qr.close_all", "pool.stop", "engine.stop", "engines.dispose", "lock.release"]
        for label, observation in result["singles"].items():
            with self.subTest(cleanup=label):
                self.assertEqual(observation["events"][-7:], cleanup)
                self.assertEqual(observation["exception"]["type"], "HardFailure")
                self.assertEqual(observation["exception"]["message"], "hard:" + label)
        self.assertEqual(result["multiple"]["events"][-7:], cleanup)
        self.assertEqual(result["multiple"]["exception"], {"type": "RuntimeError", "message": "first-cleanup"})
        self.assertEqual(result["body_only"]["exception"], {"type": "ValueError", "message": "body-error"})
        self.assertEqual(result["body_and_cleanup"]["exception"], {"type": "RuntimeError", "message": "cleanup-wins"})
        self.assertEqual(result["startup_and_cleanup"]["exception"], {"type": "RuntimeError", "message": "cleanup-wins-startup"})

    def test_isolation_audit_keeps_effects_inside_temporary_root(self):
        result = self._run_child("isolation")
        temp_root = Path(result["temp_root"])
        self.assertEqual(Path(result["cwd"]), temp_root)
        for path in result["env_paths"].values():
            self.assertTrue(Path(path).is_relative_to(temp_root))
        for path in result["touched"]:
            self.assertTrue(Path(path).is_relative_to(temp_root))
        self.assertEqual(result["forbidden_imports"], [])
        self.assertEqual(result["network_modules"], [])
        self.assertEqual(result["events"][0:2], ["env.load", "fastapi.new"])


if __name__ == "__main__":
    unittest.main()
