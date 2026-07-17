import io
import tempfile
import unittest
from pathlib import Path

from ops.supervisor_windows import (
    RotatingBinaryWriter,
    build_command,
    load_supervisor_config,
    pump_output,
)


class RotatingBinaryWriterTest(unittest.TestCase):
    def test_supervisor_loads_env_file_without_overriding_process_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / '.env'
            log_dir = Path(temp_dir) / 'logs-from-file'
            env_path.write_text(
                f'HOST=127.0.0.3\nPORT=38201\nXHS_LOG_DIR={log_dir}\n',
                encoding='utf-8',
            )
            environ = {
                'XHS_ENV_FILE': str(env_path),
                'PORT': '38202',
                'XHS_PYTHON': 'python-from-process.exe',
            }

            config = load_supervisor_config(environ=environ)
            command = build_command(config)

        self.assertEqual(config.host, '127.0.0.3')
        self.assertEqual(config.port, '38202')
        self.assertEqual(config.log_dir, str(log_dir))
        self.assertEqual(command[0], 'python-from-process.exe')
        self.assertEqual(command[-5:], ['--host', '127.0.0.3', '--port', '38202', '--headless'])

    def test_supervisor_rejects_invalid_port_before_restart_loop(self):
        for port in ('', 'not-a-port', '0', '65536'):
            with self.subTest(port=port), tempfile.TemporaryDirectory() as temp_dir:
                env_path = Path(temp_dir) / '.env'
                env_path.write_text('', encoding='utf-8')
                environ = {
                    'XHS_ENV_FILE': str(env_path),
                    'PORT': port,
                }

                with self.assertRaisesRegex(
                    ValueError,
                    'PORT must be an integer between 1 and 65535',
                ):
                    load_supervisor_config(environ=environ)

    def test_rotates_large_write_and_keeps_only_configured_backups(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "service.log"

            with RotatingBinaryWriter(str(log_path), max_bytes=8, backup_count=2) as log:
                log.write(b"abcdefghijklmnopqrstuvwx")
                log.flush()

                self.assertEqual(log_path.read_bytes(), b"qrstuvwx")
                self.assertEqual(Path(f"{log_path}.1").read_bytes(), b"ijklmnop")
                self.assertEqual(Path(f"{log_path}.2").read_bytes(), b"abcdefgh")

                log.write(b"yz")
                log.flush()

            self.assertEqual(log_path.read_bytes(), b"yz")
            self.assertEqual(Path(f"{log_path}.1").read_bytes(), b"qrstuvwx")
            self.assertEqual(Path(f"{log_path}.2").read_bytes(), b"ijklmnop")
            self.assertFalse(Path(f"{log_path}.3").exists())
            for path in Path(temp_dir).iterdir():
                self.assertLessEqual(path.stat().st_size, 8)

    def test_appends_to_existing_log_until_it_reaches_the_limit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "service.log"
            log_path.write_bytes(b"existing")

            with RotatingBinaryWriter(str(log_path), max_bytes=10, backup_count=2) as log:
                log.write(b"12")
                log.flush()

            self.assertEqual(log_path.read_bytes(), b"existing12")
            self.assertFalse(Path(f"{log_path}.1").exists())

    def test_rejects_invalid_rotation_limits(self):
        with self.assertRaises(ValueError):
            RotatingBinaryWriter("unused.log", max_bytes=0)
        with self.assertRaises(ValueError):
            RotatingBinaryWriter("unused.log", backup_count=0)

    def test_pump_output_preserves_bytes_and_closes_the_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "service.log"
            source = io.BufferedReader(io.BytesIO(b"stdout-data"), buffer_size=4)

            with RotatingBinaryWriter(str(log_path), max_bytes=8, backup_count=2) as log:
                pump_output(source, log)

            self.assertTrue(source.closed)
            self.assertEqual(log_path.read_bytes(), b"ata")
            self.assertEqual(Path(f"{log_path}.1").read_bytes(), b"stdout-d")


if __name__ == "__main__":
    unittest.main()
