import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from service.runtime_lock import RuntimeLock


ROOT = Path(__file__).resolve().parents[1]
_TOTAL_TIMEOUT = 10
_CLEANUP_RESERVE = 2
_CONTENTION_ERROR = (
    "Another XHS crawler service instance is already running for this "
    "runtime directory."
)
_CHILD_SCRIPT = r"""
import os
import sys
from pathlib import Path

from service.runtime_lock import RuntimeLock


def signal(path, value):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    os.replace(temporary, path)


lock = RuntimeLock(sys.argv[1])
ready_path = Path(sys.argv[2])
released_path = Path(sys.argv[3])
try:
    lock.acquire()
    signal(ready_path, str(os.getpid()))
    if sys.stdin.readline().strip() != "release":
        raise RuntimeError("expected release command")
    lock.release()
    signal(released_path, str(os.getpid()))
    if sys.stdin.readline().strip() != "exit":
        raise RuntimeError("expected exit command")
finally:
    lock.release()
"""


def _child_environment(env_file_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    python_path = [str(ROOT)]
    if env.get("PYTHONPATH"):
        python_path.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(python_path)
    env["XHS_ENV_FILE"] = str(env_file_path)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _send(process: subprocess.Popen[str], command: str) -> None:
    if process.stdin is None or process.stdin.closed:
        raise AssertionError("runtime-lock child stdin is unavailable")
    process.stdin.write(command + "\n")
    process.stdin.flush()


def _remaining(deadline: float, reserve: float = 0) -> float:
    return max(0.01, deadline - time.monotonic() - reserve)


class RuntimeLockTests(unittest.TestCase):
    def _wait_for_signal(
        self,
        path: Path,
        process: subprocess.Popen[str],
        signal_name: str,
        deadline: float,
    ) -> str:
        signal_deadline = deadline - _CLEANUP_RESERVE
        while time.monotonic() < signal_deadline:
            if path.exists():
                return path.read_text(encoding="utf-8")
            if process.poll() is not None:
                stdout, stderr = process.communicate(
                    timeout=_remaining(deadline, _CLEANUP_RESERVE)
                )
                self.fail(
                    f"runtime-lock child exited before {signal_name}: "
                    f"code={process.returncode}, stdout={stdout!r}, stderr={stderr!r}"
                )
            time.sleep(0.01)
        self.fail(f"timed out waiting for runtime-lock child {signal_name}")

    def test_cross_process_contention_release_and_reacquisition(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            deadline = time.monotonic() + _TOTAL_TIMEOUT
            temporary_root = Path(temporary_directory)
            lock_path = temporary_root / "runtime" / "service.lock"
            ready_path = temporary_root / "ready"
            released_path = temporary_root / "released"
            env_file_path = temporary_root / "empty.env"
            env_file_path.write_text("", encoding="utf-8")
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-B",
                    "-c",
                    _CHILD_SCRIPT,
                    str(lock_path),
                    str(ready_path),
                    str(released_path),
                ],
                cwd=ROOT,
                env=_child_environment(env_file_path),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            release_sent = False
            exit_sent = False
            parent_lock = None
            try:
                child_pid = self._wait_for_signal(
                    ready_path, process, "readiness", deadline
                )
                self.assertEqual(child_pid, str(process.pid))
                self.assertIsNone(process.poll(), "lock holder exited after readiness")

                contender = RuntimeLock(str(lock_path))
                try:
                    with self.assertRaises(RuntimeError) as raised:
                        contender.acquire()
                    self.assertEqual(str(raised.exception), _CONTENTION_ERROR)
                finally:
                    contender.release()

                _send(process, "release")
                release_sent = True
                released_pid = self._wait_for_signal(
                    released_path, process, "release", deadline
                )
                self.assertEqual(released_pid, child_pid)
                self.assertIsNone(process.poll(), "child exited instead of staying alive")
                self.assertEqual(lock_path.read_text(encoding="utf-8"), child_pid)

                parent_lock = RuntimeLock(str(lock_path))
                parent_lock.acquire()
                self.assertIsNone(process.poll(), "child exited before reacquisition")
                parent_lock.release()
                parent_lock.release()
                self.assertEqual(
                    lock_path.read_text(encoding="utf-8"), str(os.getpid())
                )

                _send(process, "exit")
                exit_sent = True
                stdout, stderr = process.communicate(
                    timeout=_remaining(deadline, _CLEANUP_RESERVE)
                )
                self.assertEqual(process.returncode, 0, stderr)
                self.assertEqual(stdout, "")
                self.assertEqual(stderr, "")
            finally:
                if parent_lock is not None:
                    parent_lock.release()
                if process.poll() is None:
                    try:
                        if not release_sent:
                            _send(process, "release")
                        if not exit_sent:
                            _send(process, "exit")
                        process.wait(timeout=_remaining(deadline, 1))
                    except (BrokenPipeError, OSError, subprocess.TimeoutExpired):
                        process.kill()
                        process.wait(timeout=_remaining(deadline))


if __name__ == "__main__":
    unittest.main()
