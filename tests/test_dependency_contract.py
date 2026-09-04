import re
import tomllib
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = ROOT / "pyproject.toml"
REQUIREMENTS_PATH = ROOT / "requirements.txt"

_EXPORT_HEADER = (
    "# Checked compatibility export of pyproject.toml [project].dependencies."
)
_PROJECT_NAME = re.compile(
    r"^([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)(?=$|\s|\[|@|[<>=!~])"
)


def _read_utf8_text(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise AssertionError(f"{path.name} must not contain a UTF-8 BOM")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise AssertionError(f"{path.name} must be valid UTF-8") from error


def _canonical_dependencies() -> list[str]:
    project = tomllib.loads(_read_utf8_text(PYPROJECT_PATH))["project"]
    dependencies = project["dependencies"]
    if not isinstance(dependencies, list) or not all(
        isinstance(item, str) and item for item in dependencies
    ):
        raise AssertionError("[project].dependencies must be nonempty strings")
    return dependencies


def _export_dependencies(text: str) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _terminal_newline_suffix(text: str) -> str:
    return re.search(r"[\r\n]*\Z", text).group(0)


def _normalized_names(dependencies: list[str], source: str) -> list[str]:
    names = []
    for dependency in dependencies:
        match = _PROJECT_NAME.match(dependency)
        if match is None:
            raise AssertionError(
                f"{source} has a directive or malformed dependency: {dependency!r}"
            )
        names.append(re.sub(r"[-_.]+", "-", match.group(1)).lower())
    return names


class DependencyContractTests(unittest.TestCase):
    def test_requirements_is_exact_ordered_export(self):
        text = _read_utf8_text(REQUIREMENTS_PATH)

        self.assertIn(
            _terminal_newline_suffix(text),
            {"\n", "\r\n"},
            "requirements.txt must have exactly one terminal newline",
        )
        self.assertEqual(text.splitlines()[0], _EXPORT_HEADER)
        self.assertEqual(_export_dependencies(text), _canonical_dependencies())

    def test_terminal_newline_contract_covers_lf_and_crlf(self):
        for ending in ("\n", "\r\n"):
            with self.subTest(accepted=repr(ending)):
                self.assertIn(_terminal_newline_suffix(f"entry{ending}"), {"\n", "\r\n"})

        for ending in ("", "\n\n", "\r\n\r\n", "\r\n\n"):
            with self.subTest(rejected=repr(ending)):
                self.assertNotIn(
                    _terminal_newline_suffix(f"entry{ending}"), {"\n", "\r\n"}
                )

    def test_dependency_names_are_unique_after_normalization(self):
        manifests = {
            "pyproject.toml": _canonical_dependencies(),
            "requirements.txt": _export_dependencies(
                _read_utf8_text(REQUIREMENTS_PATH)
            ),
        }
        for source, dependencies in manifests.items():
            with self.subTest(source=source):
                names = _normalized_names(dependencies, source)
                duplicates = sorted(
                    name for name, count in Counter(names).items() if count > 1
                )
                self.assertEqual(duplicates, [], source)


if __name__ == "__main__":
    unittest.main()
