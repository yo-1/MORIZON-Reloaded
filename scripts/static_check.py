#!/usr/bin/env python3
from __future__ import annotations

import configparser
import compileall
import re
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT

# Flat repository layout: the plugin source lives at the repository root
# alongside non-plugin directories (docs, scripts, prompts, ...). These are
# excluded from plugin-content checks and from the distribution ZIP.
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


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def is_plugin_path(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    return relative.parts[0] not in EXCLUDED_TOP_LEVEL


def main() -> None:
    required = [
        PLUGIN / "__init__.py",
        PLUGIN / "metadata.txt",
        PLUGIN / "README.md",
        PLUGIN / "NOTICE",
        PLUGIN / "LICENSE",
        PLUGIN / "CHANGELOG.md",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        fail("missing required files: " + ", ".join(missing))

    exclude_rx = re.compile(
        r"[\\/](?:%s)(?:[\\/]|$)" % "|".join(re.escape(name) for name in EXCLUDED_TOP_LEVEL)
    )
    with tempfile.TemporaryDirectory(prefix="morizon-pycache-") as cache_dir:
        previous_cache_prefix = sys.pycache_prefix
        sys.pycache_prefix = cache_dir
        try:
            if not compileall.compile_dir(str(PLUGIN), rx=exclude_rx, quiet=1):
                fail("Python syntax compilation failed")
        finally:
            sys.pycache_prefix = previous_cache_prefix

    parser = configparser.ConfigParser(interpolation=None)
    parser.read(PLUGIN / "metadata.txt", encoding="utf-8")
    general = parser["general"]
    for key in ("name", "version", "qgisMinimumVersion", "author", "repository"):
        if not general.get(key, "").strip():
            fail(f"metadata key is empty: {key}")

    if general.get("name") != "MORIZON Reloaded":
        fail("unexpected plugin name")
    if "GNU GENERAL PUBLIC LICENSE" not in (PLUGIN / "LICENSE").read_text(encoding="utf-8"):
        fail("GPL license text was not detected")

    forbidden = {"__pycache__", ".pytest_cache", ".DS_Store"}
    hits = sorted(
        str(path.relative_to(ROOT))
        for path in PLUGIN.rglob("*")
        if path.name in forbidden and is_plugin_path(path)
    )
    if hits:
        fail("generated files present: " + ", ".join(hits))

    plugin_py_count = sum(1 for path in PLUGIN.rglob("*.py") if is_plugin_path(path))
    print(f"OK: {general['name']} {general['version']}")
    print(f"OK: {plugin_py_count} plugin Python files compiled")


if __name__ == "__main__":
    main()
