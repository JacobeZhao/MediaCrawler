import contextlib
import io
import tempfile
import traceback
import unittest
from pathlib import Path
from unittest import mock

from service.runtime_env import EnvFileError, load_env_file, load_root_env


class RuntimeEnvTest(unittest.TestCase):
    def test_missing_file_is_a_noop(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            environ = {}
            result = load_env_file(Path(temp_dir) / "missing.env", environ=environ)

        self.assertFalse(result.found)
        self.assertEqual(result.loaded_count, 0)
        self.assertEqual(result.skipped_count, 0)
        self.assertEqual(environ, {})

    def test_process_values_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / ".env"
            path.write_text("EXISTING=from-file\n", encoding="utf-8")
            environ = {"EXISTING": "from-process"}
            result = load_env_file(path, environ=environ)

        self.assertEqual(result.loaded_count, 0)
        self.assertEqual(result.skipped_count, 1)
        self.assertEqual(environ['EXISTING'], 'from-process')

    def test_empty_process_value_is_not_overwritten(self):
        result, environ = self._load_bytes(
            b'EXISTING=from-file\n',
            environ={'EXISTING': ''},
        )

        self.assertEqual(result.loaded_count, 0)
        self.assertEqual(result.skipped_count, 1)
        self.assertEqual(environ['EXISTING'], '')

    def test_process_value_names_are_case_insensitive(self):
        result, environ = self._load_bytes(
            b'EXISTING=from-file\n',
            environ={'existing': 'from-process'},
        )

        self.assertEqual(result.loaded_count, 0)
        self.assertEqual(result.skipped_count, 1)
        self.assertEqual(environ, {'existing': 'from-process'})

    def test_explicit_missing_env_file_fails_instead_of_using_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = Path(temp_dir) / 'missing.env'
            environ = {'XHS_ENV_FILE': str(missing_path)}
            with self.assertRaises(EnvFileError) as raised:
                load_root_env(environ=environ)

        self.assertIn(str(missing_path), str(raised.exception))
        self.assertIn('not found', str(raised.exception))
        self.assertEqual(environ, {'XHS_ENV_FILE': str(missing_path)})

    def test_relative_env_selector_is_anchored_to_project_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir) / 'project'
            env_path = project_root / 'config' / 'service.env'
            env_path.parent.mkdir(parents=True)
            env_path.write_text('FROM_RELATIVE=file\n', encoding='utf-8')
            environ = {'xhs_env_file': 'config/service.env'}

            with (
                mock.patch('service.runtime_env.PROJECT_ROOT', project_root),
                mock.patch(
                    'service.runtime_env.DEFAULT_ENV_PATH',
                    project_root / '.env',
                ),
            ):
                result = load_root_env(environ=environ)

        self.assertTrue(result.found)
        self.assertEqual(environ['FROM_RELATIVE'], 'file')

    def test_bom_crlf_export_quotes_and_first_equals_are_supported(self):
        quote = bytes([34])
        payload = (
            b'\xef\xbb\xbfexport FILE_ONLY = from-file\r\n'
            b'EMPTY=\r\nQUOTED=' + quote + b' spaced value ' + quote + b'\r\n'
            b'FIRST_EQUALS=a=b=c\r\n'
        )
        result, environ = self._load_bytes(payload)

        self.assertEqual(result.loaded_count, 4)
        self.assertEqual(environ['FILE_ONLY'], 'from-file')
        self.assertEqual(environ['EMPTY'], '')
        self.assertEqual(environ['QUOTED'], ' spaced value ')
        self.assertEqual(environ['FIRST_EQUALS'], 'a=b=c')

    def test_comments_and_shell_like_text_remain_data(self):
        marker = chr(35)
        tick = chr(96)
        literal = 'C:\\temp\\$HOME\\' + tick + 'echo' + tick + '\\$' + '(noop)'
        payload = (
            f'{marker} comment\nINLINE=value {marker} comment\n'
            f'QUOTED=\'literal {marker} value\'\nLITERAL={literal}\n'
        ).encode()
        result, environ = self._load_bytes(payload)

        self.assertEqual(result.loaded_count, 3)
        self.assertEqual(environ['INLINE'], 'value')
        self.assertEqual(environ['QUOTED'], f'literal {marker} value')
        self.assertEqual(environ['LITERAL'], literal)

    def test_quote_comment_and_backslash_rules_are_explicit(self):
        payload = (
            b'FRAGMENT=value#fragment\n'
            b'COMMENT=value \t# comment\n'
            b'HASH=#fragment\n'
            b'EMPTY= # comment\n'
            b'QUOTED="value # = text" # comment\n'
            b'WINDOWS="C:\\temp\\new\\$HOME\\n"\n'
            b"EMPTY_QUOTED=''\n"
        )
        result, environ = self._load_bytes(payload)

        self.assertEqual(result.loaded_count, 7)
        self.assertEqual(environ['FRAGMENT'], 'value#fragment')
        self.assertEqual(environ['COMMENT'], 'value')
        self.assertEqual(environ['HASH'], '#fragment')
        self.assertEqual(environ['EMPTY'], '')
        self.assertEqual(environ['QUOTED'], 'value # = text')
        self.assertEqual(environ['WINDOWS'], 'C:\\temp\\new\\$HOME\\n')
        self.assertEqual(environ['EMPTY_QUOTED'], '')

    def test_reloading_never_overwrites_existing_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / '.env'
            path.write_text('FIRST=one\n', encoding='utf-8')
            environ = {}
            first = load_env_file(path, environ=environ)
            path.write_text('FIRST=changed\nSECOND=two\n', encoding='utf-8')
            second = load_env_file(path, environ=environ)

        self.assertEqual(first.loaded_count, 1)
        self.assertEqual(second.loaded_count, 1)
        self.assertEqual(second.skipped_count, 1)
        self.assertEqual(environ, {'FIRST': 'one', 'SECOND': 'two'})

    def test_invalid_files_are_atomic_and_do_not_leak_values(self):
        sentinel = 'do-not-leak-this-value'
        cases = (
            f'GOOD=ok\nBROKEN {sentinel}\n'.encode(),
            f'DUP=first\nDUP={sentinel}\n'.encode(),
            f'GOOD=ok\nBAD={sentinel}\x00\n'.encode(),
            f'GOOD=ok\nBAD="{sentinel}\n'.encode(),
            f"GOOD=ok\nBAD='{sentinel}\n".encode(),
            f'GOOD=ok\nBAD="ok"{sentinel}\n'.encode(),
            f'GOOD=ok\n9BAD={sentinel}\n'.encode(),
            f'GOOD=ok\nSECRET={sentinel}'.encode() + b'\xff\n',
        )

        for payload in cases:
            with self.subTest(payload_length=len(payload)):
                self._assert_invalid(
                    payload,
                    sentinel,
                    environ={'EXISTING': 'keep', 'GOOD': 'from-process'},
                )

    def test_duplicate_export_name_is_rejected_before_merging(self):
        self._assert_invalid(
            b'_LEADING=value\nexport _leading=other\n',
            'other',
            environ={'_LEADING': 'from-process'},
        )

    def test_env_file_selector_must_come_from_process_environment(self):
        for name in ('XHS_ENV_FILE', 'xhs_env_file'):
            with self.subTest(name=name):
                self._assert_invalid(
                    f'GOOD=ok\n{name}=do-not-follow-this-path\n'.encode(),
                    'do-not-follow-this-path',
                )

    def test_success_is_silent_and_result_contains_counts_only(self):
        sentinel = 'successful-secret-value'
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            result, environ = self._load_bytes(f'SECRET={sentinel}\n'.encode())

        self.assertEqual(environ['SECRET'], sentinel)
        self.assertEqual(output.getvalue(), '')
        self.assertNotIn(sentinel, repr(result))
        self.assertNotIn('SECRET', repr(result))

    def _load_bytes(self, payload: bytes, environ=None):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / ".env"
            path.write_bytes(payload)
            target = {} if environ is None else environ
            result = load_env_file(path, environ=target)
        return result, target

    def _assert_invalid(self, payload: bytes, sentinel: str, environ=None):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / '.env'
            path.write_bytes(payload)
            target = {} if environ is None else dict(environ)
            before = dict(target)
            output = io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                with self.assertRaises(EnvFileError) as raised:
                    load_env_file(path, environ=target)

        rendered = ''.join(
            traceback.format_exception(
                type(raised.exception),
                raised.exception,
                raised.exception.__traceback__,
            )
        )
        self.assertEqual(target, before)
        self.assertIn(str(path), str(raised.exception))
        self.assertNotIn(sentinel, str(raised.exception))
        self.assertNotIn(sentinel, repr(raised.exception))
        self.assertNotIn(sentinel, rendered)
        self.assertNotIn(sentinel, output.getvalue())
        self.assertIsNone(raised.exception.__context__)
