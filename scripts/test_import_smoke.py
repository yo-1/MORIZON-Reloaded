#!/usr/bin/env python3
"""Smoke-import the plugin entry point with minimal QGIS dependency stubs."""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]


def module(name: str, **members):
    result = types.ModuleType(name)
    result.__dict__.update(members)
    sys.modules[name] = result
    return result


def main() -> None:
    sys.dont_write_bytecode = True
    qgis = module("qgis")
    qgis.__path__ = []
    pyqt = module("qgis.PyQt")
    pyqt.__path__ = []
    pyqt.QtCore = module("qgis.PyQt.QtCore", Qt=MagicMock())
    module("qgis.PyQt.QtGui", QAction=MagicMock, QIcon=MagicMock)
    module("qgis.core", QgsProject=MagicMock)

    # The entry point imports these modules, but their behavior belongs to
    # the real-QGIS smoke test (qgis_import_smoke.py). Stub only that boundary.
    package = module("MORIZON")
    package.__path__ = [str(ROOT)]
    module("MORIZON.diag_log", UiStallWatchdog=MagicMock,
           count_event=MagicMock, register_dialog_visibility_check=MagicMock,
           timed=MagicMock())
    module("MORIZON.forest_zoning_main_dialog", ForestZoningMainDialog=MagicMock)
    module("MORIZON.forest_zoning_settings_dialog", ForestZoningSettingsDialog=MagicMock)
    module("MORIZON.branding", DISPLAY_NAME="MORIZON Reloaded", asset_path=MagicMock)

    entry = importlib.import_module("MORIZON.forest_zoning")
    if not callable(entry.ForestZoning):
        raise AssertionError("ForestZoning entry point is missing")
    # Load the real package initializer, which provides QGIS classFactory.
    source = (ROOT / "__init__.py").read_text(encoding="utf-8")
    exec(compile(source, str(ROOT / "__init__.py"), "exec"), package.__dict__)
    instance = package.classFactory(MagicMock())
    if not isinstance(instance, entry.ForestZoning):
        raise AssertionError("classFactory did not construct the plugin")
    print("OK: plugin entry module imported and classFactory constructed ForestZoning")


if __name__ == "__main__":
    main()
