#!/usr/bin/env python3
"""Package the plugin ZIP and redistributable Windows validation materials."""

from __future__ import annotations

import configparser
import hashlib
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "test_data" / "ZoningKit_SYNTH" / "DATA"
PREFIX = "MORIZON_QGIS344_VALIDATION"


def main() -> Path:
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(ROOT / "metadata.txt", encoding="utf-8")
    version = parser["general"]["version"]
    plugin_zip = ROOT / "dist" / f"MORIZON_Reloaded_QGIS344_v{version}.zip"
    if not plugin_zip.is_file():
        raise FileNotFoundError(f"先に scripts/build_plugin_zip.py を実行: {plugin_zip}")
    if not DATA.is_dir():
        raise FileNotFoundError(DATA)

    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    items = {
        f"plugin/{plugin_zip.name}": plugin_zip.read_bytes(),
        "WINDOWS_QGIS344_RUNBOOK.md": (
            ROOT / "docs" / "WINDOWS_QGIS344_RUNBOOK.md"
        ).read_bytes(),
        "RESULTS_TEMPLATE.md": (
            ROOT / "docs" / "WINDOWS_QGIS344_RESULTS_TEMPLATE.md"
        ).read_bytes(),
        "windows_validation_snapshot.py": (
            ROOT / "scripts" / "windows_validation_snapshot.py"
        ).read_bytes(),
        "SOURCE_COMMIT.txt": (source_commit + "\n").encode("utf-8"),
    }
    for path in sorted(DATA.rglob("*")):
        if path.is_file() and path.name != ".gitkeep":
            relative = path.relative_to(DATA).as_posix()
            items[f"synthetic/ZoningKit_SYNTH/DATA/{relative}"] = path.read_bytes()

    manifest = "".join(
        f"{hashlib.sha256(content).hexdigest()}  {name}\n"
        for name, content in sorted(items.items())
    )
    items["MANIFEST_SHA256.txt"] = manifest.encode("utf-8")
    output = ROOT / "dist" / f"MORIZON_QGIS344_v{version}_validation_bundle.zip"
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for directory in ("synthetic/ZoningKit_SYNTH/YOUSO/",
                          "synthetic/ZoningKit_SYNTH/ZONING/"):
            archive.writestr(f"{PREFIX}/{directory}", b"")
        for name, content in sorted(items.items()):
            archive.writestr(f"{PREFIX}/{name}", content)
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or not all(
            name.startswith(PREFIX + "/") for name in names
        ):
            raise ValueError("検証用ZIPの構造が不正です")
        for entry in manifest.splitlines():
            digest, name = entry.split("  ", 1)
            if hashlib.sha256(archive.read(f"{PREFIX}/{name}")).hexdigest() != digest:
                raise ValueError(f"検証用ZIPの内容が一致しません: {name}")
    print(output)
    return output


if __name__ == "__main__":
    main()
