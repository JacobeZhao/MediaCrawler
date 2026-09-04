import ast
import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETTINGS_PATH = ROOT / "config" / "settings.py"
SAMPLE_PATH = ROOT / ".env.example"
DOCS_PATH = ROOT / "docs" / "config.md"

_HELPER_TYPES = {
    "_bool_env": bool,
    "_int_env": int,
    "_float_env": float,
}
_SERVICE_SAMPLE_OVERRIDES = {
    "HEADLESS": True,
    "CDP_CONNECT_EXISTING": False,
}
_CONSTRUCTED_PATH_DEFAULTS = {
    "SQLITE_DB_PATH",
    "SERVICE_DB_PATH",
    "RUNTIME_LOCK_PATH",
}
_SAMPLE_ONLY_INPUTS = {"XHS_COOKIES"}


def _literal(node):
    return node.value if isinstance(node, ast.Constant) else None


def _is_os_environ_get(call: ast.Call) -> bool:
    func = call.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "get"
        and isinstance(func.value, ast.Attribute)
        and func.value.attr == "environ"
        and isinstance(func.value.value, ast.Name)
        and func.value.value.id == "os"
    )


def _settings_contract() -> dict[str, tuple[type, object]]:
    tree = ast.parse(SETTINGS_PATH.read_text(encoding="utf-8"))
    settings_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Settings"
    )
    contract: dict[str, tuple[type, object]] = {}
    for call in (node for node in ast.walk(settings_class) if isinstance(node, ast.Call)):
        value_type = None
        if isinstance(call.func, ast.Name) and call.func.id in _HELPER_TYPES:
            value_type = _HELPER_TYPES[call.func.id]
        elif _is_os_environ_get(call):
            value_type = str
        if value_type is None or not call.args:
            continue

        name = _literal(call.args[0])
        if not isinstance(name, str):
            continue
        default = _literal(call.args[1]) if len(call.args) > 1 else None
        if name in contract:
            raise AssertionError(f"duplicate Settings environment input: {name}")
        contract[name] = (value_type, default)
    return contract


def _sample_values() -> dict[str, str]:
    values: dict[str, str] = {}
    pattern = re.compile(r"^\s*(?:#\s*)?([A-Z][A-Z0-9_]*)=(.*)$")
    for line in SAMPLE_PATH.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if not match:
            continue
        name, value = match.groups()
        if name in values:
            raise AssertionError(f"duplicate sample input: {name}")
        values[name] = value
    return values


def _coerce_sample(value: str, value_type: type):
    if value_type is bool:
        normalized = value.lower()
        if normalized not in {"true", "false"}:
            raise ValueError(f"expected boolean sample value, got {value!r}")
        return normalized == "true"
    return value_type(value)


class ConfigContractTests(unittest.TestCase):
    def test_sample_exhaustively_covers_application_settings(self):
        contract = _settings_contract()
        sample = _sample_values()

        self.assertEqual(set(sample), set(contract) | _SAMPLE_ONLY_INPUTS)
        self.assertEqual(sample["XHS_COOKIES"], "")
        self.assertEqual(sample["JUSTONEAPI_TOKEN"], "")

    def test_sample_defaults_and_documented_exceptions_are_stable(self):
        contract = _settings_contract()
        sample = _sample_values()
        docs = " ".join(DOCS_PATH.read_text(encoding="utf-8").split())

        self.assertEqual(
            {name: _coerce_sample(sample[name], contract[name][0])
             for name in _SERVICE_SAMPLE_OVERRIDES},
            _SERVICE_SAMPLE_OVERRIDES,
        )
        for name, (value_type, default) in contract.items():
            if name in _SERVICE_SAMPLE_OVERRIDES or name in _CONSTRUCTED_PATH_DEFAULTS:
                continue
            self.assertIsNotNone(default, name)
            self.assertEqual(_coerce_sample(sample[name], value_type), default, name)

        for name in contract:
            self.assertIn(f"`{name}`", docs, name)

        for statement in (
            "exhaustive application-setting inventory",
            "HEADLESS=true",
            "CDP_CONNECT_EXISTING=false",
            "XHS_COOKIES",
            "XHS_ENV_FILE",
            "XHS_PYTHON",
            "XHS_LOG_DIR",
            "XHS_RESTART_DELAY_SECONDS",
            "ops/README.md",
        ):
            self.assertIn(statement, docs)

    def test_runtime_artifacts_are_ignored_but_source_cache_is_tracked(self):
        ignored = (
            ".env",
            ".venv/probe",
            "data/probe",
            "browser_data/probe",
            "exports/probe",
            "logs/probe.log",
            "database/probe.db",
            "database/probe.db-shm",
            "database/probe.db-wal",
            "service/probe.db",
            "service/probe.db-shm",
            "service/probe.db-wal",
            "__pycache__/probe.pyc",
            "dist/probe",
            "build/probe",
        )
        for path in ignored:
            with self.subTest(path=path):
                completed = self._git("check-ignore", "--no-index", "--quiet", "--", path)
                self.assertEqual(completed.returncode, 0, completed.stderr)

        cache_check = self._git(
            "check-ignore", "--no-index", "--quiet", "--", "cache/local_cache.py"
        )
        self.assertEqual(cache_check.returncode, 1, cache_check.stderr)
        tracked_check = self._git(
            "ls-files", "--error-unmatch", "--", "cache/local_cache.py"
        )
        self.assertEqual(tracked_check.returncode, 0, tracked_check.stderr)

    @staticmethod
    def _git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )


if __name__ == "__main__":
    unittest.main()
