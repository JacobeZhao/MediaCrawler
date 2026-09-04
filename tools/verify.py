import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPILE_TARGETS = (
    "service",
    "config",
    "media_platform",
    "store",
    "database",
    "tools",
    "base",
    "cache",
    "model",
    "start_xhs_service.py",
)


def verification_phases() -> tuple[tuple[str, list[str]], ...]:
    python = [sys.executable, "-B"]
    return (
        (
            "dependency contract",
            python
            + [
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_dependency_contract.py",
                "-v",
            ],
        ),
        (
            "configuration contract",
            python
            + [
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_config_contract.py",
                "-v",
            ],
        ),
        ("compileall", python + ["-m", "compileall", "-q", *COMPILE_TARGETS]),
        (
            "full unittest discovery",
            python + ["-m", "unittest", "discover", "-s", "tests", "-v"],
        ),
    )


def verification_environment(
    env_file_path: str, bytecode_path: str
) -> dict[str, str]:
    env = os.environ.copy()
    python_path = [str(ROOT)]
    if env.get("PYTHONPATH"):
        python_path.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(python_path)
    env["XHS_ENV_FILE"] = env_file_path
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPYCACHEPREFIX"] = bytecode_path
    return env


def run() -> int:
    results = []
    with tempfile.TemporaryDirectory(prefix="mediacrawler-verify-") as temporary:
        temporary_path = Path(temporary)
        env_file_path = temporary_path / "empty.env"
        bytecode_path = temporary_path / "pycache"
        env_file_path.write_text("", encoding="utf-8")
        bytecode_path.mkdir()
        env = verification_environment(str(env_file_path), str(bytecode_path))
        for label, command in verification_phases():
            print(f"==> {label}", flush=True)
            completed = subprocess.run(
                command,
                cwd=ROOT,
                env=env,
                check=False,
                shell=False,
            )
            results.append((label, completed.returncode))

    print("==> verification summary", flush=True)
    for label, returncode in results:
        print(f"{label}: {'pass' if returncode == 0 else f'fail ({returncode})'}")
    return int(any(returncode != 0 for _, returncode in results))


if __name__ == "__main__":
    raise SystemExit(run())
