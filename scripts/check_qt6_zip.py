#!/usr/bin/env python3
"""Run the QGIS plugin website's Qt6 validator on a distribution ZIP."""

from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path

IMAGE = "ghcr.io/qgis/pyqgis4-checker:main-ubuntu"
HEADER = "=== dry_run mode | Start Logs ==="


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--image", default=IMAGE)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="morizon-qt6-") as tmp:
        root = Path(tmp)
        with zipfile.ZipFile(args.zip_path) as archive:
            archive.extractall(root)
        files = list((root / "MORIZON").rglob("*.py"))
        if not files:
            raise ValueError("ZIP contains no MORIZON Python modules")

        # TemporaryDirectory uses mode 0700. The checker image runs as a
        # non-root user, so an unreadable mount would silently scan 0 files.
        for directory, subdirs, filenames in os.walk(root):
            os.chmod(directory, 0o755)
            for filename in filenames:
                os.chmod(Path(directory) / filename, 0o644)

        check_count = (
            f'test "$(find /plugin -name "*.py" | wc -l)" -eq {len(files)}'
        )
        command = [
            "docker", "run", "--rm", "--network", "none",
            "--mount", f"type=bind,src={root},dst=/plugin,readonly",
            "--entrypoint", "sh", args.image, "-c",
            check_count + " && exec /usr/local/bin/pyqt5_to_pyqt6.py /plugin --dry_run",
        ]
        result = subprocess.run(command, text=True, capture_output=True)
        output = (result.stdout + result.stderr).strip()
        findings = [line for line in output.splitlines() if line != HEADER]
        print(f"Qt6 checker scanned {len(files)} Python files; findings: {len(findings)}")
        for line in findings:
            print(line)
        if result.returncode or findings or HEADER not in output:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
