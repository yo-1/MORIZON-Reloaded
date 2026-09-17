"""Build and verify a deterministic, QGIS-installable MORIZON ZIP archive."""

from __future__ import annotations

import configparser
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIRECTORY = REPOSITORY_ROOT / "dist"
PLUGIN_DIRECTORY = "MORIZON"
EXCLUDED_TOP_LEVEL = {".git", ".github", "dist"}
EXCLUDED_NAMES = {".DS_Store", "Thumbs.db", "__pycache__"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
REQUIRED_ARCHIVE_FILES = {
    f"{PLUGIN_DIRECTORY}/__init__.py",
    f"{PLUGIN_DIRECTORY}/LICENSE",
    f"{PLUGIN_DIRECTORY}/NOTICE",
    f"{PLUGIN_DIRECTORY}/README.md",
    f"{PLUGIN_DIRECTORY}/metadata.txt",
}
FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def plugin_version() -> str:
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(REPOSITORY_ROOT / "metadata.txt", encoding="utf-8-sig")
    version = parser.get("general", "version").strip()
    if not re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z._+-]*", version):
        raise ValueError(f"Unsafe plugin version for filename: {version!r}")
    return version


def distributable_files() -> list[Path]:
    files: list[Path] = []
    for path in REPOSITORY_ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(REPOSITORY_ROOT)
        if relative.parts[0] in EXCLUDED_TOP_LEVEL:
            continue
        if any(part in EXCLUDED_NAMES for part in relative.parts):
            continue
        if path.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(REPOSITORY_ROOT).as_posix())


def write_archive(archive_path: Path) -> None:
    with zipfile.ZipFile(
        archive_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for source_path in distributable_files():
            relative = source_path.relative_to(REPOSITORY_ROOT)
            archive_name = PurePosixPath(PLUGIN_DIRECTORY, *relative.parts).as_posix()
            info = zipfile.ZipInfo(archive_name, FIXED_ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source_path.read_bytes(), compresslevel=9)


def verify_archive(archive_path: Path) -> None:
    with zipfile.ZipFile(archive_path, mode="r") as archive:
        names = archive.namelist()
        name_set = set(names)
        if len(names) != len(name_set):
            raise ValueError("ZIP archive contains duplicate entries")
        if archive.testzip() is not None:
            raise ValueError("ZIP CRC validation failed")

    missing = sorted(REQUIRED_ARCHIVE_FILES - name_set)
    if missing:
        raise ValueError(f"ZIP archive is missing required entries: {', '.join(missing)}")

    invalid = sorted(
        name
        for name in names
        if not name.startswith(f"{PLUGIN_DIRECTORY}/")
        or "\\" in name
        or name.startswith(f"{PLUGIN_DIRECTORY}/.github/")
        or name.startswith(f"{PLUGIN_DIRECTORY}/dist/")
        or "/__pycache__/" in name
        or name.endswith((".pyc", ".pyo"))
    )
    if invalid:
        raise ValueError("ZIP archive contains invalid entries:\n" + "\n".join(invalid))

    print(f"ZIP structure: OK ({len(names)} files)")


def main() -> int:
    try:
        version = plugin_version()
        OUTPUT_DIRECTORY.mkdir(exist_ok=True)
        for stale_archive in OUTPUT_DIRECTORY.glob("MORIZON_Reloaded_QGIS344_v*.zip"):
            stale_archive.unlink()

        archive_path = OUTPUT_DIRECTORY / f"MORIZON_Reloaded_QGIS344_v{version}.zip"
        write_archive(archive_path)
        verify_archive(archive_path)
        print(f"Created: {archive_path.relative_to(REPOSITORY_ROOT)}")
        print(f"Size: {archive_path.stat().st_size} bytes")
    except (configparser.Error, OSError, ValueError, zipfile.BadZipFile) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
