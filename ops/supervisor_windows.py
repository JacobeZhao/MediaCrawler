import os
import subprocess
import sys
import threading
import time
from collections.abc import MutableMapping
from dataclasses import dataclass
from typing import BinaryIO


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from service.runtime_env import load_root_env


LOG_MAX_BYTES = 20 * 1024 * 1024
LOG_BACKUP_COUNT = 5
PIPE_READ_SIZE = 64 * 1024


@dataclass(frozen=True)
class SupervisorConfig:
    python: str
    host: str
    port: str
    log_dir: str
    restart_delay_seconds: int


def load_supervisor_config(
    *,
    environ: MutableMapping[str, str] | None = None,
) -> SupervisorConfig:
    target = os.environ if environ is None else environ
    load_root_env(environ=target)
    try:
        restart_delay_seconds = int(target.get('XHS_RESTART_DELAY_SECONDS', '5'))
    except ValueError:
        raise ValueError('XHS_RESTART_DELAY_SECONDS must be an integer') from None
    try:
        port_number = int(target.get('PORT', '8088'))
    except ValueError:
        raise ValueError('PORT must be an integer between 1 and 65535') from None
    if not 1 <= port_number <= 65535:
        raise ValueError('PORT must be an integer between 1 and 65535')

    return SupervisorConfig(
        python=target.get(
            'XHS_PYTHON',
            os.path.join(ROOT, '.venv', 'Scripts', 'python.exe'),
        ),
        host=target.get('HOST', '0.0.0.0'),
        port=str(port_number),
        log_dir=target.get('XHS_LOG_DIR', os.path.join(ROOT, 'logs')),
        restart_delay_seconds=restart_delay_seconds,
    )


class RotatingBinaryWriter:
    def __init__(
        self,
        path: str,
        max_bytes: int = LOG_MAX_BYTES,
        backup_count: int = LOG_BACKUP_COUNT,
    ):
        if max_bytes <= 0:
            raise ValueError("max_bytes must be greater than zero")
        if backup_count <= 0:
            raise ValueError("backup_count must be greater than zero")

        self.path = path
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self._stream: BinaryIO | None = None
        self._size = 0

    def __enter__(self):
        self._open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def _open(self):
        self._stream = open(self.path, "ab")
        self._size = os.path.getsize(self.path)

    def _backup_path(self, index: int) -> str:
        return f"{self.path}.{index}"

    def _rotate(self):
        self.close()

        oldest_backup = self._backup_path(self.backup_count)
        if os.path.exists(oldest_backup):
            os.remove(oldest_backup)

        for index in range(self.backup_count - 1, 0, -1):
            source = self._backup_path(index)
            if os.path.exists(source):
                os.replace(source, self._backup_path(index + 1))

        if os.path.exists(self.path):
            os.replace(self.path, self._backup_path(1))
        self._open()

    def write(self, data: bytes):
        if self._stream is None:
            raise ValueError("write to closed log")

        remaining = memoryview(data)
        while remaining:
            if self._size >= self.max_bytes:
                self._rotate()

            chunk_size = min(len(remaining), self.max_bytes - self._size)
            chunk = remaining[:chunk_size]
            written = self._stream.write(chunk)
            if written != chunk_size:
                raise OSError(f"incomplete log write: {written} of {chunk_size} bytes")
            self._size += written
            remaining = remaining[written:]

    def flush(self):
        if self._stream is not None:
            self._stream.flush()

    def close(self):
        if self._stream is not None:
            self._stream.close()
            self._stream = None


def pump_output(source: BinaryIO, destination: RotatingBinaryWriter):
    try:
        while chunk := source.read1(PIPE_READ_SIZE):
            destination.write(chunk)
            destination.flush()
    finally:
        source.close()


def build_command(config: SupervisorConfig) -> list[str]:
    return [
        config.python,
        os.path.join(ROOT, "start_xhs_service.py"),
        "--host",
        config.host,
        "--port",
        config.port,
        "--headless",
    ]


def main():
    config = load_supervisor_config()
    os.makedirs(config.log_dir, exist_ok=True)
    supervisor_log = os.path.join(config.log_dir, "service-supervisor.log")
    stdout_log = os.path.join(config.log_dir, f"service-{config.port}.log")
    stderr_log = os.path.join(config.log_dir, f"service-{config.port}.err.log")

    with (
        RotatingBinaryWriter(supervisor_log) as sup,
        RotatingBinaryWriter(stdout_log) as out,
        RotatingBinaryWriter(stderr_log) as err,
    ):
        sup.write(b"supervisor starting\n")
        sup.flush()
        while True:
            child = subprocess.Popen(
                build_command(config),
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if child.stdout is None or child.stderr is None:
                raise RuntimeError("failed to capture child output")

            stdout_pump = threading.Thread(
                target=pump_output,
                args=(child.stdout, out),
                name="service-stdout-pump",
            )
            stderr_pump = threading.Thread(
                target=pump_output,
                args=(child.stderr, err),
                name="service-stderr-pump",
            )
            stdout_pump.start()
            stderr_pump.start()

            sup.write(f"child pid {child.pid}\n".encode("utf-8"))
            sup.flush()
            rc = child.wait()
            stdout_pump.join()
            stderr_pump.join()
            sup.write(f"child exited {rc}\n".encode("utf-8"))
            sup.flush()
            time.sleep(config.restart_delay_seconds)


if __name__ == "__main__":
    main()
