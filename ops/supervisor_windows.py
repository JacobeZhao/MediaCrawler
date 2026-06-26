import os
import subprocess
import time


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = os.environ.get("XHS_PYTHON", os.path.join(ROOT, ".venv", "Scripts", "python.exe"))
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = os.environ.get("PORT", "8088")
LOG_DIR = os.environ.get("XHS_LOG_DIR", os.path.join(ROOT, "logs"))
RESTART_DELAY_SECONDS = int(os.environ.get("XHS_RESTART_DELAY_SECONDS", "5"))


def build_command() -> list[str]:
    return [
        PYTHON,
        os.path.join(ROOT, "start_xhs_service.py"),
        "--host",
        HOST,
        "--port",
        PORT,
        "--headless",
    ]


def main():
    os.makedirs(LOG_DIR, exist_ok=True)
    supervisor_log = os.path.join(LOG_DIR, "service-supervisor.log")
    stdout_log = os.path.join(LOG_DIR, f"service-{PORT}.log")
    stderr_log = os.path.join(LOG_DIR, f"service-{PORT}.err.log")

    with open(supervisor_log, "ab") as sup:
        sup.write(b"supervisor starting\n")
        sup.flush()
        while True:
            with open(stdout_log, "ab") as out, open(stderr_log, "ab") as err:
                child = subprocess.Popen(
                    build_command(),
                    cwd=ROOT,
                    stdin=subprocess.DEVNULL,
                    stdout=out,
                    stderr=err,
                )
                sup.write(f"child pid {child.pid}\n".encode("utf-8"))
                sup.flush()
                rc = child.wait()
                sup.write(f"child exited {rc}\n".encode("utf-8"))
                sup.flush()
            time.sleep(RESTART_DELAY_SECONDS)


if __name__ == "__main__":
    main()
