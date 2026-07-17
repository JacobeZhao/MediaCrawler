import os
import re
from collections.abc import MutableMapping
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = PROJECT_ROOT / '.env'
ENV_FILE_VARIABLE = 'XHS_ENV_FILE'
_ENV_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]*\Z')


class EnvFileError(ValueError):
    def __init__(self, path: Path, line_number: int | None, reason: str):
        location = f'{path}:{line_number}' if line_number is not None else str(path)
        super().__init__(f'{location}: {reason}')
        self.path = path
        self.line_number = line_number
        self.reason = reason


@dataclass(frozen=True)
class EnvLoadResult:
    found: bool
    loaded_count: int
    skipped_count: int


def load_root_env(
    *,
    environ: MutableMapping[str, str] | None = None,
) -> EnvLoadResult:
    target = os.environ if environ is None else environ
    configured_path = _get_environment_value(target, ENV_FILE_VARIABLE)
    if not configured_path:
        return load_env_file(DEFAULT_ENV_PATH, environ=target)

    path = Path(configured_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    result = load_env_file(path, environ=target)
    if not result.found:
        raise EnvFileError(path, None, 'configured environment file was not found')
    return result


def load_env_file(
    path: str | Path,
    *,
    environ: MutableMapping[str, str] | None = None,
) -> EnvLoadResult:
    env_path = Path(path)
    target = os.environ if environ is None else environ

    try:
        payload = env_path.read_bytes()
    except FileNotFoundError:
        return EnvLoadResult(found=False, loaded_count=0, skipped_count=0)
    except OSError:
        raise EnvFileError(env_path, None, 'could not read environment file') from None

    values = _parse_env_file(payload, env_path)
    existing_names = {_canonical_name(name) for name in target}
    loaded_count = 0
    skipped_count = 0
    for name, value in values.items():
        canonical_name = _canonical_name(name)
        if canonical_name in existing_names:
            skipped_count += 1
            continue
        target.setdefault(name, value)
        existing_names.add(canonical_name)
        loaded_count += 1

    return EnvLoadResult(
        found=True,
        loaded_count=loaded_count,
        skipped_count=skipped_count,
    )


def _parse_env_file(payload: bytes, path: Path) -> dict[str, str]:
    text, decode_error_line = _decode_env_file(payload)
    if text is None:
        raise EnvFileError(path, decode_error_line, 'invalid UTF-8')

    values: dict[str, str] = {}
    seen_names: set[str] = set()
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        statement = raw_line.strip()
        if not statement or statement.startswith('#'):
            continue
        if '\x00' in raw_line:
            raise EnvFileError(path, line_number, 'NUL byte is not allowed')

        if statement == 'export' or (
            statement.startswith('export') and statement[6:7].isspace()
        ):
            statement = statement[6:].lstrip()

        if '=' not in statement:
            raise EnvFileError(path, line_number, 'expected KEY=VALUE assignment')

        name, raw_value = statement.split('=', 1)
        name = name.strip()
        if not _ENV_NAME.fullmatch(name):
            raise EnvFileError(path, line_number, 'invalid environment variable name')
        canonical_name = _canonical_name(name)
        if canonical_name == ENV_FILE_VARIABLE:
            raise EnvFileError(
                path,
                line_number,
                'environment file selector must be set in the process environment',
            )
        if canonical_name in seen_names:
            raise EnvFileError(path, line_number, 'duplicate environment variable name')

        seen_names.add(canonical_name)
        values[name] = _parse_value(raw_value, path, line_number)

    return values


def _decode_env_file(payload: bytes) -> tuple[str | None, int | None]:
    try:
        return payload.decode('utf-8-sig'), None
    except UnicodeDecodeError as exc:
        line_number = payload[: exc.start].count(b'\n') + 1
        return None, line_number


def _canonical_name(name: str) -> str:
    return name.upper()


def _get_environment_value(
    environ: MutableMapping[str, str],
    name: str,
) -> str | None:
    if name in environ:
        return environ[name]
    canonical_name = _canonical_name(name)
    return next(
        (
            value
            for existing_name, value in environ.items()
            if _canonical_name(existing_name) == canonical_name
        ),
        None,
    )


def _parse_value(raw_value: str, path: Path, line_number: int) -> str:
    value = raw_value.lstrip()
    if not value:
        return ''

    if value[0] in ('"', "'"):
        quote = value[0]
        closing_index = value.find(quote, 1)
        if closing_index < 0:
            raise EnvFileError(path, line_number, 'unterminated quoted value')

        tail = value[closing_index + 1 :]
        if tail:
            if not tail[0].isspace():
                raise EnvFileError(path, line_number, 'unexpected text after quoted value')
            tail = tail.lstrip()
            if tail and not tail.startswith('#'):
                raise EnvFileError(path, line_number, 'unexpected text after quoted value')
        return value[1:closing_index]

    for index, character in enumerate(raw_value):
        if character == '#' and index > 0 and raw_value[index - 1].isspace():
            raw_value = raw_value[:index]
            break
    return raw_value.strip()
