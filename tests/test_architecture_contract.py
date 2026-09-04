import ast
import importlib.util
import json
import os
import site
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

FACADE_SUBSETS = {
    "service/domain/__init__.py": {
        "CanonicalComment", "CanonicalCreator", "CanonicalNote", "CrawlResult",
    },
    "service/executors/__init__.py": {
        "ExecutionContext", "ExecutorLeaseLost", "ExecutorPaused",
        "ExecutorRegistry", "JustOneApiTaskExecutor", "LocalTaskExecutor",
        "ProviderReadiness", "TaskExecutor",
    },
    "service/schemas/__init__.py": {
        "AccountCookieRequest", "AccountQrcodeStartRequest", "AccountRequest",
        "BatchCreatorTaskRequest", "BatchSearchTaskRequest", "CookieRequest",
        "CreatorTaskRequest", "NoteItem", "NoteTaskRequest", "SearchTaskRequest",
    },
    "service/providers/justoneapi/__init__.py": {
        "ApiEnvelope", "JustOneApiBalanceError", "JustOneApiClient",
        "JustOneApiCredentialError", "JustOneApiDailyQuotaError", "JustOneApiError",
        "JustOneApiInvalidRequestError", "JustOneApiRateLimitError",
        "JustOneApiTokenLimitError", "JustOneApiUnknownOutcomeError",
        "JustOneApiUpstreamError", "RequestRecord",
    },
    "service/routes/__init__.py": {
        "accounts", "export", "login", "notes", "proxies", "status", "tasks",
    },
}

ROUTE_ACCESSORS = {
    "accounts.py": {"get_account_service"},
    "export.py": {"get_export_service"},
    "login.py": {"get_engine"},
    "notes.py": {"get_note_query_service"},
    "proxies.py": {"get_proxy_service"},
    "status.py": {"get_engine", "get_pool", "get_task_manager"},
    "tasks.py": {"get_task_service"},
}

WILDCARD_COMPATIBILITY_FACADES = {
    "config/__init__.py": {"base_config", "db_config"},
    "media_platform/xhs/__init__.py": {"field"},
}


def _tree(relative_path):
    path = ROOT / relative_path
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _literal_all(tree):
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(target, ast.Name) and target.id == "__all__" for target in targets):
            continue
        value = ast.literal_eval(node.value)
        if not isinstance(value, (list, tuple)) or not all(isinstance(item, str) for item in value):
            raise AssertionError("__all__ must be a literal string sequence")
        return list(value)
    raise AssertionError("missing __all__")


def _top_level_bindings(tree):
    bindings = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            bindings.update(alias.asname or alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            bindings.update(alias.asname or alias.name for alias in node.names if alias.name != "*")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bindings.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            bindings.update(target.id for target in targets if isinstance(target, ast.Name))
    return bindings


def _module_name(path):
    relative = path.relative_to(ROOT).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _resolved_imports(path):
    module_name = _module_name(path)
    package = module_name if path.name == "__init__.py" else module_name.rpartition(".")[0]
    imports = set()
    for node in ast.walk(_tree(path.relative_to(ROOT))):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = importlib.util.resolve_name(
                    "." * node.level + (node.module or ""), package
                )
            else:
                base = node.module or ""
            if node.module:
                imports.add(base)
            else:
                imports.update(f"{base}.{alias.name}" for alias in node.names)
    return imports


def _has_prefix(imports, prefixes):
    return {
        imported
        for imported in imports
        if any(imported == prefix or imported.startswith(prefix + ".") for prefix in prefixes)
    }


class ArchitectureContractTests(unittest.TestCase):
    def test_package_facade_subsets_are_unique_and_bound(self):
        lazy_executor_names = {"LocalTaskExecutor", "JustOneApiTaskExecutor"}
        for relative_path, expected_subset in FACADE_SUBSETS.items():
            with self.subTest(path=relative_path):
                tree = _tree(relative_path)
                exports = _literal_all(tree)
                self.assertEqual(len(exports), len(set(exports)))
                self.assertLessEqual(expected_subset, set(exports))
                eager_subset = set(expected_subset)
                if relative_path == "service/executors/__init__.py":
                    eager_subset -= lazy_executor_names
                self.assertLessEqual(eager_subset, _top_level_bindings(tree))

        executor_tree = _tree("service/executors/__init__.py")
        lazy_branches = {
            comparator.value
            for node in ast.walk(executor_tree)
            if isinstance(node, ast.Compare)
            for comparator in node.comparators
            if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str)
        }
        self.assertLessEqual(lazy_executor_names, lazy_branches)

        app_tree = _tree("service/app.py")
        imports_create_app = any(
            isinstance(node, ast.ImportFrom)
            and node.module == "main"
            and node.level == 1
            and any(alias.name == "create_app" for alias in node.names)
            for node in app_tree.body
        )
        app_calls = [
            node.value
            for node in app_tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "app" for target in node.targets)
        ]
        self.assertTrue(imports_create_app)
        self.assertEqual(len(app_calls), 1)
        self.assertIsInstance(app_calls[0], ast.Call)
        self.assertIsInstance(app_calls[0].func, ast.Name)
        self.assertEqual(app_calls[0].func.id, "create_app")

    def test_wildcard_compatibility_facades_preserve_static_shape(self):
        for relative_path, expected_modules in WILDCARD_COMPATIBILITY_FACADES.items():
            with self.subTest(path=relative_path):
                tree = _tree(relative_path)
                wildcard_modules = {
                    node.module
                    for node in tree.body
                    if isinstance(node, ast.ImportFrom)
                    and node.level == 1
                    and len(node.names) == 1
                    and node.names[0].name == "*"
                }
                self.assertEqual(wildcard_modules, expected_modules)
                self.assertFalse(
                    any(
                        isinstance(target, ast.Name) and target.id == "__all__"
                        for node in tree.body
                        if isinstance(node, (ast.Assign, ast.AnnAssign))
                        for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
                    )
                )

        config_tree = _tree("config/__init__.py")
        explicit_imports = {
            (node.module, alias.name, alias.asname)
            for node in config_tree.body
            if isinstance(node, ast.ImportFrom)
            and node.level == 1
            for alias in node.names
            if alias.name != "*"
        }
        self.assertEqual(explicit_imports, {("settings", "settings", None)})

    def test_dependency_safe_facades_import_without_runtime_infrastructure(self):
        child = r'''
import json
import sys
from service.domain import CanonicalComment, CanonicalCreator, CanonicalNote, CrawlResult
from service.executors import (
    ExecutionContext, ExecutorLeaseLost, ExecutorPaused, ExecutorRegistry,
    ProviderReadiness, TaskExecutor,
)

names = {
    CanonicalComment.__name__, CanonicalCreator.__name__, CanonicalNote.__name__,
    CrawlResult.__name__, ExecutionContext.__name__, ExecutorLeaseLost.__name__,
    ExecutorPaused.__name__, ExecutorRegistry.__name__, ProviderReadiness.__name__,
    TaskExecutor.__name__,
}
expected = {
    "CanonicalComment", "CanonicalCreator", "CanonicalNote", "CrawlResult",
    "ExecutionContext", "ExecutorLeaseLost", "ExecutorPaused", "ExecutorRegistry",
    "ProviderReadiness", "TaskExecutor",
}
forbidden = ("service.crawler_engine", "service.account_pool", "service.service_db", "playwright", "aiosqlite", "sqlalchemy")
loaded = sorted(name for name in sys.modules if name == forbidden or any(name == prefix or name.startswith(prefix + ".") for prefix in forbidden))
print("RESULT=" + json.dumps({"names": sorted(names), "expected": sorted(expected), "loaded": loaded}))
'''
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
                [sys.executable, "-B", "-c", child],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
                shell=False,
            )
        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
        )
        result_lines = [line for line in completed.stdout.splitlines() if line.startswith("RESULT=")]
        self.assertEqual(len(result_lines), 1)
        result = json.loads(result_lines[0][7:])
        self.assertEqual(result["names"], result["expected"])
        self.assertEqual(result["loaded"], [])

    def test_provider_dependency_direction_is_one_way(self):
        justone_path = ROOT / "service" / "executors" / "justoneapi.py"
        local_path = ROOT / "service" / "executors" / "local.py"
        justone_imports = _resolved_imports(justone_path)
        local_imports = _resolved_imports(local_path)

        self.assertLessEqual(
            {
                "service.service_db", "store.xhs", "service.domain",
                "service.providers.justoneapi.client",
                "service.providers.justoneapi.normalizer",
                "service.executors.base",
            },
            justone_imports,
        )
        local_edges = {
            "service.service_db", "service.account_pool", "service.circuit_breaker",
            "service.crawler_engine", "service.rate_limiter", "service.executors.base",
        }
        self.assertLessEqual(local_edges, local_imports)

        local_infrastructure = {
            "service.account_pool", "service.circuit_breaker", "service.crawler_engine",
            "service.rate_limiter", "service.executors.local", "media_platform.xhs", "playwright",
        }
        self.assertEqual(_has_prefix(justone_imports, local_infrastructure), set())
        self.assertEqual(_has_prefix(local_imports, {"service.providers.justoneapi"}), set())

        provider_imports = set()
        for path in (ROOT / "service" / "providers" / "justoneapi").glob("*.py"):
            provider_imports.update(_resolved_imports(path))
        self.assertIn("service.domain", provider_imports)
        self.assertEqual(_has_prefix(provider_imports, local_infrastructure), set())

        shared_imports = set()
        for filename in ("base.py", "registry.py"):
            shared_imports.update(_resolved_imports(ROOT / "service" / "executors" / filename))
        self.assertEqual(
            _has_prefix(
                shared_imports,
                {"service.executors.local", "service.executors.justoneapi", "service.providers", "service.account_pool", "service.crawler_engine"},
            ),
            set(),
        )

    def test_routes_preserve_dependency_accessor_boundary(self):
        routes_dir = ROOT / "service" / "routes"
        for filename, expected_accessors in ROUTE_ACCESSORS.items():
            with self.subTest(route=filename):
                path = routes_dir / filename
                tree = _tree(path.relative_to(ROOT))
                dependency_imports = {
                    alias.name
                    for node in ast.walk(tree)
                    if isinstance(node, ast.ImportFrom)
                    and node.level == 2
                    and node.module == "dependencies"
                    for alias in node.names
                }
                self.assertEqual(dependency_imports, expected_accessors)
                called = {
                    node.func.id
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                }
                self.assertLessEqual(expected_accessors, called)

                imports = _resolved_imports(path)
                self.assertEqual(
                    _has_prefix(imports, {"service.services", "service.executors", "service.providers"}),
                    set(),
                )
                sql = {
                    node.value
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Constant)
                    and isinstance(node.value, str)
                    and any(keyword in node.value.upper() for keyword in ("SELECT ", "INSERT ", "UPDATE ", "DELETE ", "CREATE ", "ALTER "))
                }
                self.assertEqual(sql, set())


if __name__ == "__main__":
    unittest.main()
