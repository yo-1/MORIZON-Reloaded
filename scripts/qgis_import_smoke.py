#!/usr/bin/env python3
"""Import every module from the built plugin ZIP in an initialized QGIS."""

import argparse
import importlib
import sys
import tempfile
import zipfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("zip_path", type=Path)
    args = parser.parse_args()

    sys.path.extend(["/usr/share/qgis/python", "/usr/share/qgis/python/plugins"])
    from qgis.core import Qgis, QgsApplication

    QgsApplication.setPrefixPath("/usr", True)
    app = QgsApplication([], False)
    app.initQgis()
    with tempfile.TemporaryDirectory(prefix="morizon-qgis-smoke-") as tmp:
        with zipfile.ZipFile(args.zip_path) as archive:
            archive.extractall(tmp)
        sys.path.insert(0, tmp)
        paths = sorted((Path(tmp) / "MORIZON").rglob("*.py"))
        for path in paths:
            relative = path.relative_to(tmp).with_suffix("")
            parts = list(relative.parts)
            if parts[-1] == "__init__":
                parts.pop()
            importlib.import_module(".".join(parts))
        print(f"QGIS {Qgis.QGIS_VERSION}: imported {len(paths)} plugin modules")
    app.exitQgis()


if __name__ == "__main__":
    main()
