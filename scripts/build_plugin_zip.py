#!/usr/bin/env python3
from __future__ import annotations

import configparser
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT
PLUGIN_ZIP_ROOT = "MORIZON"
DIST = ROOT / "dist"

# Flat repository layout: everything under these top-level names is
# documentation/tooling, not plugin content, and must not ship in the
# distribution ZIP.
EXCLUDED_TOP_LEVEL = {
    ".git",
    ".github",
    ".gitignore",
    "docs",
    "scripts",
    "prompts",
    "references",
    "original",
    "dist",
    "CLAUDE.md",
}
EXCLUDED_PARTS = {"__pycache__", ".pytest_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def main() -> None:
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(PLUGIN / "metadata.txt", encoding="utf-8")
    version = parser["general"]["version"]
    DIST.mkdir(exist_ok=True)
    output = DIST / f"MORIZON_Reloaded_QGIS344_v{version}.zip"

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PLUGIN.rglob("*")):
            if path.is_dir():
                continue
            relative = path.relative_to(ROOT)
            if relative.parts[0] in EXCLUDED_TOP_LEVEL:
                continue
            if EXCLUDED_PARTS.intersection(relative.parts) or path.suffix in EXCLUDED_SUFFIXES:
                continue
            archive_path = Path(PLUGIN_ZIP_ROOT) / relative
            archive.write(path, archive_path.as_posix())

    with zipfile.ZipFile(output) as archive:
        roots = {name.split("/", 1)[0] for name in archive.namelist()}
        if roots != {PLUGIN_ZIP_ROOT}:
            raise SystemExit(f"invalid ZIP roots: {sorted(roots)}")
    print(output)


if __name__ == "__main__":
    main()
