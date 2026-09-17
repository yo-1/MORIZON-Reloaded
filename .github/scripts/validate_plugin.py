"""Dependency-free static validation for the MORIZON QGIS plugin package."""

from __future__ import annotations

import configparser
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXCLUDED_TOP_LEVEL = {".git", ".github", "dist"}
REQUIRED_ROOT_FILES = {
    "__init__.py",
    "LICENSE",
    "NOTICE",
    "README.md",
    "metadata.txt",
}
REQUIRED_METADATA_KEYS = {
    "name",
    "qgisminimumversion",
    "qgismaximumversion",
    "description",
    "version",
    "icon",
    "author",
    "email",
    "homepage",
    "tracker",
    "repository",
}


def distribution_files(pattern: str) -> list[Path]:
    """Return distributable files matching a glob, excluding CI/build content."""
    return sorted(
        path
        for path in REPOSITORY_ROOT.rglob(pattern)
        if path.is_file()
        and path.relative_to(REPOSITORY_ROOT).parts[0] not in EXCLUDED_TOP_LEVEL
        and "__pycache__" not in path.parts
    )


def validate_required_files() -> None:
    missing = sorted(
        name for name in REQUIRED_ROOT_FILES if not (REPOSITORY_ROOT / name).is_file()
    )
    if missing:
        raise ValueError(f"Missing required plugin files: {', '.join(missing)}")
    print(f"Required root files: OK ({len(REQUIRED_ROOT_FILES)})")


def validate_python_syntax() -> None:
    python_files = distribution_files("*.py")
    if not python_files:
        raise ValueError("No distributable Python files were found")

    failures: list[str] = []
    for path in python_files:
        relative = path.relative_to(REPOSITORY_ROOT)
        try:
            source = path.read_text(encoding="utf-8-sig")
            compile(source, str(relative), "exec")
        except (OSError, SyntaxError, UnicodeError) as error:
            failures.append(f"{relative}: {error}")

    if failures:
        raise ValueError("Python syntax validation failed:\n" + "\n".join(failures))
    print(f"Python syntax: OK ({len(python_files)} files)")


def validate_ui_xml() -> None:
    ui_files = distribution_files("*.ui")
    if not ui_files:
        raise ValueError("No Qt Designer .ui files were found")

    failures: list[str] = []
    for path in ui_files:
        relative = path.relative_to(REPOSITORY_ROOT)
        try:
            root = ET.parse(path).getroot()
            if root.tag != "ui":
                failures.append(f"{relative}: root element is {root.tag!r}, expected 'ui'")
        except (OSError, ET.ParseError) as error:
            failures.append(f"{relative}: {error}")

    if failures:
        raise ValueError("Qt UI XML validation failed:\n" + "\n".join(failures))
    print(f"Qt UI XML: OK ({len(ui_files)} files)")


def validate_metadata() -> None:
    metadata_path = REPOSITORY_ROOT / "metadata.txt"
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    parser.optionxform = str.lower
    with metadata_path.open("r", encoding="utf-8-sig") as metadata_file:
        parser.read_file(metadata_file)

    if not parser.has_section("general"):
        raise ValueError("metadata.txt has no [general] section")

    general = parser["general"]
    missing = sorted(key for key in REQUIRED_METADATA_KEYS if not general.get(key, "").strip())
    if missing:
        raise ValueError(f"metadata.txt is missing required values: {', '.join(missing)}")

    minimum_version = tuple(int(part) for part in general["qgisminimumversion"].split("."))
    if minimum_version < (3, 44):
        raise ValueError("qgisMinimumVersion must be 3.44 or later for MORIZON Reloaded")

    icon_path = REPOSITORY_ROOT / Path(general["icon"])
    if not icon_path.is_file():
        raise ValueError(f"metadata icon does not exist: {general['icon']}")

    for key in ("homepage", "tracker", "repository"):
        if not general[key].startswith("https://"):
            raise ValueError(f"metadata {key} must use an https:// URL")

    print(
        "metadata.txt: OK "
        f"(version={general['version']}, qgisMinimumVersion={general['qgisminimumversion']})"
    )


def main() -> int:
    checks = (
        validate_required_files,
        validate_python_syntax,
        validate_ui_xml,
        validate_metadata,
    )
    try:
        for check in checks:
            check()
    except (configparser.Error, OSError, UnicodeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("All static plugin checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
