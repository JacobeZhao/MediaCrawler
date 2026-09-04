import ast
import importlib
import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools import verify


_STANDARD_LIBRARY_IMPORTS = {
    "os",
    "pathlib",
    "subprocess",
    "sys",
    "tempfile",
}
TESTING_DOCS_PATH = verify.ROOT / "docs" / "testing.md"
AI_CHANGE_GUIDE_PATH = verify.ROOT / "docs" / "ai-change-guide.md"


class VerificationTests(unittest.TestCase):
    def test_import_is_dependency_free_and_does_not_execute(self):
        tree = ast.parse(Path(verify.__file__).read_text(encoding="utf-8"))
        imports = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports.update(
            node.module.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        self.assertEqual(imports, _STANDARD_LIBRARY_IMPORTS)

        with patch("subprocess.run") as subprocess_run:
            importlib.reload(verify)
        subprocess_run.assert_not_called()

    def test_phases_have_fixed_order_commands_and_current_interpreter(self):
        phases = verify.verification_phases()
        self.assertEqual(
            [label for label, _ in phases],
            [
                "dependency contract",
                "configuration contract",
                "compileall",
                "full unittest discovery",
            ],
        )
        for _, command in phases:
            self.assertEqual(command[:2], [sys.executable, "-B"])

        self.assertEqual(
            phases[0][1][-4:], ["tests", "-p", "test_dependency_contract.py", "-v"]
        )
        self.assertEqual(
            phases[1][1][-4:], ["tests", "-p", "test_config_contract.py", "-v"]
        )
        self.assertEqual(
            phases[2][1],
            [sys.executable, "-B", "-m", "compileall", "-q", *verify.COMPILE_TARGETS],
        )
        self.assertEqual(
            phases[3][1],
            [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"],
        )

        testing_docs = TESTING_DOCS_PATH.read_text(encoding="utf-8")
        ai_change_guide = AI_CHANGE_GUIDE_PATH.read_text(encoding="utf-8")
        self.assertIn("```powershell\npython -m tools.verify\n```", testing_docs)
        self.assertIn(
            "python -m unittest discover -s tests -p "
            "test_dependency_contract.py -v",
            testing_docs,
        )
        self.assertNotIn(r".\.venv\Scripts\python.exe", testing_docs)
        self.assertIn("`python -m tools.verify`", ai_change_guide)

    def test_environment_is_isolated_without_mutating_parent(self):
        original = os.environ.copy()
        with patch.dict(os.environ, {"PYTHONPATH": "existing-path"}, clear=True):
            env = verify.verification_environment("empty-env", "outside-bytecode")
            self.assertEqual(os.environ, {"PYTHONPATH": "existing-path"})

        self.assertEqual(os.environ, original)
        self.assertEqual(env["XHS_ENV_FILE"], "empty-env")
        self.assertEqual(env["PYTHONDONTWRITEBYTECODE"], "1")
        self.assertEqual(env["PYTHONPYCACHEPREFIX"], "outside-bytecode")
        self.assertEqual(
            env["PYTHONPATH"].split(os.pathsep), [str(verify.ROOT), "existing-path"]
        )

    def test_run_executes_every_phase_and_aggregates_status(self):
        phases = verify.verification_phases()
        results = [SimpleNamespace(returncode=7)] + [
            SimpleNamespace(returncode=0) for _ in phases[1:]
        ]

        def run_phase(command, **kwargs):
            env = kwargs["env"]
            env_file_path = Path(env["XHS_ENV_FILE"])
            bytecode_path = Path(env["PYTHONPYCACHEPREFIX"])
            self.assertTrue(env_file_path.is_file())
            self.assertEqual(env_file_path.read_bytes(), b"")
            self.assertTrue(bytecode_path.is_dir())
            return results.pop(0)

        with (
            patch("tools.verify.subprocess.run", side_effect=run_phase) as subprocess_run,
            redirect_stdout(io.StringIO()) as output,
        ):
            self.assertEqual(verify.run(), 1)

        self.assertEqual(subprocess_run.call_count, len(phases))
        for invocation, (_, command) in zip(subprocess_run.call_args_list, phases):
            self.assertEqual(invocation.args, (command,))
            self.assertEqual(invocation.kwargs["cwd"], verify.ROOT)
            self.assertEqual(invocation.kwargs["check"], False)
            self.assertEqual(invocation.kwargs["shell"], False)
        self.assertIn("dependency contract: fail (7)", output.getvalue())
        self.assertIn("full unittest discovery: pass", output.getvalue())

        successes = [SimpleNamespace(returncode=0) for _ in phases]
        with (
            patch("tools.verify.subprocess.run", side_effect=successes),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(verify.run(), 0)


if __name__ == "__main__":
    unittest.main()
