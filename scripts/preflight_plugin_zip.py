#!/usr/bin/env python3
"""Run local release checks on the exact ZIP intended for QGIS upload."""

from __future__ import annotations

import argparse
import collections
import configparser
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


def run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, cwd=cwd, text=True, capture_output=True, check=False
    )


def check_zip(archive: zipfile.ZipFile, zip_path: Path) -> str:
    names = archive.namelist()
    if len(names) != len(set(names)):
        raise ValueError("ZIP contains duplicate entries")
    if not names or "MORIZON/metadata.txt" not in names:
        raise ValueError("ZIP must contain MORIZON/metadata.txt")
    for info in archive.infolist():
        path = PurePosixPath(info.filename)
        if (
            path.is_absolute()
            or ".." in path.parts
            or path.parts[0] != "MORIZON"
            or "\\" in info.filename
        ):
            raise ValueError(f"unsafe ZIP entry: {info.filename}")
        if (info.external_attr >> 16) & 0o170000 == 0o120000:
            raise ValueError(f"symlink in ZIP: {info.filename}")
        if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            raise ValueError(f"generated Python file in ZIP: {info.filename}")
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(archive.read("MORIZON/metadata.txt").decode("utf-8"))
    version = parser["general"].get("version", "").strip()
    if (
        not version
        or f"_v{version}.zip" != zip_path.name[-len(f"_v{version}.zip") :]
    ):
        raise ValueError("ZIP filename and metadata version disagree")
    return version


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip", type=Path, help="the exact ZIP to upload")
    args = parser.parse_args()
    zip_path = args.zip.resolve()
    if not zip_path.is_file():
        parser.error(f"ZIP not found: {zip_path}")

    with tempfile.TemporaryDirectory(prefix="morizon-preflight-") as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(zip_path) as archive:
            version = check_zip(archive, zip_path)
            archive.extractall(root)
        plugin = root / "MORIZON"
        env = os.environ.copy()
        env["PYTHONPYCACHEPREFIX"] = str(root / "pycache")
        compiled = subprocess.run(
            [sys.executable, "-m", "compileall", "-q", str(plugin)],
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        if compiled.returncode:
            print(compiled.stderr, file=sys.stderr)
            return 1

        # Keep literal QML style strings byte-for-byte intact; Flake8 still
        # checks every other rule in those modules.
        flake8 = run(
            [
                sys.executable, "-m", "flake8", "--max-line-length=160",
                "--extend-ignore=E203",
                "--per-file-ignores="
                "MORIZON/processes/raster_styler/distance.py:E501,"
                "MORIZON/processes/raster_styler/slope.py:E501,"
                "MORIZON/processes/raster_styler/utils.py:E501",
                "MORIZON",
            ],
            cwd=root,
        )
        if "No module named flake8" in flake8.stderr:
            raise RuntimeError("install flake8 before running this preflight")
        issues = flake8.stdout.splitlines()
        codes = collections.Counter(
            match.group(1)
            for line in issues
            if (match := re.search(r": ([A-Z][0-9]{3}) ", line))
        )
        if flake8.returncode not in (0, 1):
            raise RuntimeError(f"Flake8 failed: {flake8.stderr.strip()}")

        bandit = run(
            [
                sys.executable,
                "-m",
                "bandit",
                "-r",
                "-q",
                "-f",
                "json",
                "MORIZON",
            ],
            cwd=root,
        )
        if not bandit.stdout.strip():
            raise RuntimeError(f"Bandit failed: {bandit.stderr.strip()}")
        bandit_results = json.loads(bandit.stdout)["results"]
        serious = [
            item
            for item in bandit_results
            if item["issue_severity"] in {"MEDIUM", "HIGH"}
        ]

        secrets = run(
            [sys.executable, "-m", "detect_secrets", "scan", "MORIZON"],
            cwd=root,
        )
        if not secrets.stdout.strip():
            raise RuntimeError(
                f"detect-secrets failed: {secrets.stderr.strip()}"
            )
        secret_results = json.loads(secrets.stdout)["results"]
        secret_count = sum(map(len, secret_results.values()))

        print(f"ZIP: {zip_path.name}; plugin version: {version}")
        print(f"Python files: {len(list(plugin.rglob('*.py')))}; syntax: OK")
        print(f"Flake8: {
            len(issues)} issues; codes: {
            dict(
                codes.most_common())}")
        for issue in issues[:10]:
            print(f"  {issue}")
        print(
            f"Bandit: {len(serious)} medium/high; {len(bandit_results) - len(serious)} low"
        )
        print(f"detect-secrets: {secret_count} potential secrets")
        return 1 if issues or serious or secret_count else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        OSError,
        ValueError,
        KeyError,
        RuntimeError,
        zipfile.BadZipFile,
    ) as error:
        print(f"preflight failed: {error}", file=sys.stderr)
        raise SystemExit(2) from error
