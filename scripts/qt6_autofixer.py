#!/usr/bin/env python3
"""Replace supported legacy PyQt enum spellings in plugin Python files.

By default this overwrites changed files. Use --check in CI to fail when a
replacement is needed without mutating the checkout.
"""

from __future__ import annotations

import argparse
import io
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".git", ".github", "docs", "scripts", "prompts", "references", "original", "dist", "tests"}

ENUMS = {
    "QMessageBox": {
        "Warning": "Icon", "Information": "Icon", "Critical": "Icon",
        "Question": "Icon", "NoIcon": "Icon",
        "Ok": "StandardButton", "Yes": "StandardButton", "No": "StandardButton",
        "Cancel": "StandardButton", "Abort": "StandardButton",
        "Retry": "StandardButton", "Ignore": "StandardButton",
        "Save": "StandardButton", "Discard": "StandardButton",
        "Apply": "StandardButton", "Reset": "StandardButton",
        "AcceptRole": "ButtonRole", "RejectRole": "ButtonRole",
        "ActionRole": "ButtonRole", "YesRole": "ButtonRole",
        "NoRole": "ButtonRole", "DestructiveRole": "ButtonRole",
        "HelpRole": "ButtonRole", "ApplyRole": "ButtonRole",
        "ResetRole": "ButtonRole", "InvalidRole": "ButtonRole",
    },
    "Qt": {
        "AlignCenter": "AlignmentFlag", "AlignLeft": "AlignmentFlag",
        "AlignRight": "AlignmentFlag", "AlignTop": "AlignmentFlag",
        "AlignBottom": "AlignmentFlag", "AlignHCenter": "AlignmentFlag",
        "AlignVCenter": "AlignmentFlag", "AlignJustify": "AlignmentFlag",
        "Horizontal": "Orientation", "Vertical": "Orientation",
        "WindowStaysOnTopHint": "WindowType",
        "WindowCloseButtonHint": "WindowType",
        "WindowMinimizeButtonHint": "WindowType",
        "WindowMaximizeButtonHint": "WindowType",
        "Key_Escape": "Key", "Key_Return": "Key", "Key_Enter": "Key",
        "KeepAspectRatio": "AspectRatioMode",
        "SmoothTransformation": "TransformationMode",
    },
}


def fix_text(source: str) -> tuple[str, int]:
    """Tokenize to avoid changing comments, strings and already scoped enums."""
    tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    lines = source.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))

    def index(position):
        line, column = position
        return offsets[line - 1] + column

    edits = []
    for i in range(len(tokens) - 2):
        root, dot, member = tokens[i:i + 3]
        if root.type != tokenize.NAME or root.string not in ENUMS:
            continue
        if dot.string != "." or member.type != tokenize.NAME:
            continue
        group = ENUMS[root.string].get(member.string)
        if group is None:
            continue
        if i and tokens[i - 1].string == ".":
            continue
        edits.append((index(dot.end), f"{group}."))
    for position, addition in reversed(edits):
        source = source[:position] + addition + source[position:]
    return source, len(edits)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report needed fixes without writing")
    parser.add_argument("paths", nargs="*", type=Path, help="files or directories; default: plugin sources")
    args = parser.parse_args()
    paths = args.paths or [ROOT]
    files = sorted({file for path in paths for file in
                    (path.rglob("*.py") if path.is_dir() else [path])
                    if file.is_file() and (args.paths or file.relative_to(ROOT).parts[0] not in EXCLUDED)})
    changed = 0
    for file in files:
        with tokenize.open(file) as stream:
            source = stream.read()
            encoding = stream.encoding
        updated, count = fix_text(source)
        if count:
            changed += count
            print(f"{file}: {count} replacement(s)")
            if not args.check:
                with open(file, "w", encoding=encoding, newline="") as stream:
                    stream.write(updated)
    print(f"Scanned {len(files)} Python files; {changed} replacement(s) {'needed' if args.check else 'made'}")
    return 1 if args.check and changed else 0


if __name__ == "__main__":
    sys.exit(main())
