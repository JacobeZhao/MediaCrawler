import json
import os
import site
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
START_SCRIPT = ROOT / 'start_xhs_service.py'


class StartupConfigTest(unittest.TestCase):
    def test_start_script_uses_cli_then_process_then_env_file(self):
        runner = r'''
import json
import os
import runpy
import sys
import types

path = sys.argv[1]
entry_args = sys.argv[2:]
uvicorn = types.ModuleType('uvicorn')

def run(app, **kwargs):
    print('RESULT=' + json.dumps({
        'app': app,
        'host': kwargs['host'],
        'port': kwargs['port'],
        'headless': os.environ.get('HEADLESS'),
        'cdp': os.environ.get('CDP_CONNECT_EXISTING'),
    }))

uvicorn.run = run
sys.modules['uvicorn'] = uvicorn
sys.argv = [path, *entry_args]
runpy.run_path(path, run_name='__main__')
'''
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / '.env'
            env_path.write_text(
                'HOST=127.0.0.2\nPORT=38101\nHEADLESS=false\n',
                encoding='utf-8',
            )
            cases = (
                ({}, [], 38101, 'false', None),
                ({'PORT': '38102'}, [], 38102, 'false', None),
                (
                    {'HEADLESS': 'true', 'CDP_CONNECT_EXISTING': 'true'},
                    [],
                    38101,
                    'true',
                    'false',
                ),
                ({'PORT': 'invalid'}, ['--port', '38103'], 38103, 'false', None),
                (
                    {'PORT': '38102'},
                    ['--port', '38104', '--headless'],
                    38104,
                    'true',
                    'false',
                ),
            )

            for inherited, args, expected_port, expected_headless, expected_cdp in cases:
                with self.subTest(expected_port=expected_port):
                    env = self._isolated_env(env_path)
                    env.update(inherited)
                    completed = self._run_python(
                        ['-c', runner, str(START_SCRIPT), *args],
                        env,
                    )
                    result = self._read_result(completed.stdout)

                    self.assertEqual(result['app'], 'service.app:app')
                    self.assertEqual(result['host'], '127.0.0.2')
                    self.assertEqual(result['port'], expected_port)
                    self.assertEqual(result['headless'], expected_headless)
                    self.assertEqual(result['cdp'], expected_cdp)

    def test_service_bootstrap_loads_env_before_settings(self):
        sentinel = 'startup-secret-sentinel'
        runner = r'''
import json
import os
import service.main
from config.settings import settings

print('RESULT=' + json.dumps({
    'port': settings.port,
    'local_enabled': settings.local_crawler_enabled,
    'provider_enabled': settings.justoneapi_enabled,
    'token_matches': settings.justoneapi_token == os.environ['TEST_EXPECTED_TOKEN'],
}))
'''
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / '.env'
            env_path.write_text(
                'PORT=38111\n'
                'LOCAL_CRAWLER_ENABLED=false\n'
                'JUSTONEAPI_ENABLED=true\n'
                f'JUSTONEAPI_TOKEN={sentinel}\n',
                encoding='utf-8',
            )
            env = self._isolated_env(env_path)
            env['TEST_EXPECTED_TOKEN'] = sentinel
            completed = self._run_python(['-c', runner], env)

        result = self._read_result(completed.stdout)
        self.assertEqual(result['port'], 38111)
        self.assertFalse(result['local_enabled'])
        self.assertTrue(result['provider_enabled'])
        self.assertTrue(result['token_matches'])
        self.assertNotIn(sentinel, completed.stdout)
        self.assertNotIn(sentinel, completed.stderr)

        source = (ROOT / 'service' / 'main.py').read_text(encoding='utf-8')
        loader_call = source.index('load_root_env()')
        self.assertLess(
            loader_call,
            source.index('from config.settings import settings'),
        )
        self.assertLess(loader_call, source.index('from .dependencies import'))

    def test_runtime_env_import_does_not_freeze_application_settings(self):
        runner = (
            'import json, sys, service.runtime_env; '
            'print("RESULT=" + json.dumps({'
            '"settings": "config.settings" in sys.modules, '
            '"app": "service.app" in sys.modules}))'
        )
        completed = self._run_python(
            ['-c', runner],
            self._isolated_env(Path('unused.env')),
        )

        self.assertEqual(
            self._read_result(completed.stdout),
            {'settings': False, 'app': False},
        )

    def test_foreground_script_leaves_host_and_port_to_python(self):
        script = (ROOT / 'ops' / 'start-windows-foreground.cmd').read_text(
            encoding='utf-8',
        )

        self.assertIn('start_xhs_service.py', script)
        self.assertIn('--headless', script)
        self.assertNotIn('set PORT=', script)
        self.assertNotIn('set HOST=', script)
        self.assertNotIn('--port %PORT%', script)
        self.assertNotIn('--host %HOST%', script)
        self.assertNotIn('service-%PORT%', script)

    def _isolated_env(self, env_path: Path) -> dict[str, str]:
        env = os.environ.copy()
        for name in (
            'HOST',
            'PORT',
            'HEADLESS',
            'CDP_CONNECT_EXISTING',
            'LOCAL_CRAWLER_ENABLED',
            'JUSTONEAPI_ENABLED',
            'JUSTONEAPI_TOKEN',
            'XHS_ENV_FILE',
        ):
            env.pop(name, None)
        env['XHS_ENV_FILE'] = str(env_path)
        return env

    def _run_python(
        self,
        args: list[str],
        env: dict[str, str],
    ) -> subprocess.CompletedProcess[str]:
        child_env = env.copy()
        import_paths = [path for path in sys.path if path]
        import_paths.extend(site.getsitepackages())
        if existing := child_env.get('PYTHONPATH'):
            import_paths.append(existing)
        child_env['PYTHONPATH'] = os.pathsep.join(dict.fromkeys(import_paths))
        completed = subprocess.run(
            [sys.executable, *args],
            cwd=ROOT,
            env=child_env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            0,
            msg=f'stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}',
        )
        return completed

    def _read_result(self, stdout: str):
        for line in reversed(stdout.splitlines()):
            if line.startswith('RESULT='):
                return json.loads(line.removeprefix('RESULT='))
        self.fail(f'missing RESULT line in stdout:\n{stdout}')


if __name__ == '__main__':
    unittest.main()
