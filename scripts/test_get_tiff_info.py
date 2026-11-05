#!/usr/bin/env python3
"""QGIS-independent regression tests for utils.get_tiff_info()'s gdalinfo parsing.

Covers the 2026-11-03 Windows on-device report: a JSONDecodeError
("Expecting value: line 1 column 1 (char 0)") at elements.py:121 ->
utils/__init__.py's gdalinfo JSON parsing, three times in a row on the same
input. The real GDAL/QGIS environment that produced the failure is not
available here, so these tests exercise the parsing logic in isolation
against synthetic gdalinfo "OUTPUT" html content, not against the real
Windows DEM file. See docs/OPEN_ISSUES.md O-38 for what remains unconfirmed.
"""
from __future__ import annotations

import importlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]


def _stub_module(name: str, **members) -> types.ModuleType:
    mod = types.ModuleType(name)
    mod.__dict__.update(members)
    sys.modules[name] = mod
    return mod


def _install_qgis_stubs() -> None:
    """Install the minimal fake qgis/processing/MORIZON.* environment that
    utils/__init__.py needs to import, without a real QGIS installation.
    Mirrors the stubbing approach already used by scripts/test_import_smoke.py.
    """
    qgis = _stub_module("qgis")
    qgis.__path__ = []
    pyqt = _stub_module("qgis.PyQt")
    pyqt.__path__ = []
    _stub_module("qgis.PyQt.QtCore")
    _stub_module("qgis.PyQt.QtGui")
    _stub_module("qgis.PyQt.QtWidgets")
    _stub_module(
        "qgis.core",
        QgsCoordinateReferenceSystem=MagicMock(),
        QgsRasterLayer=MagicMock,
    )
    _stub_module("qgis.gui")
    _stub_module("processing", run=MagicMock())

    package = _stub_module("MORIZON")
    package.__path__ = [str(ROOT)]
    _stub_module("MORIZON.processes", raster_styler=MagicMock())
    _stub_module(
        "MORIZON.diag_log",
        timed=lambda *a, **k: _NullContext(),
        count_event=MagicMock(),
    )
    _stub_module("MORIZON.constants", PIXELS_THRESHOLD_RESAMPLING=25_000_000)


class _NullContext:
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


_install_qgis_stubs()
utils = importlib.import_module("MORIZON.utils")


VALID_GDALINFO_JSON = json.dumps(
    {
        "coordinateSystem": {"wkt": "LOCAL_CS[\"dummy\"]"},
        "cornerCoordinates": {
            "upperLeft": [0.0, 100.0],
            "lowerRight": [100.0, 0.0],
        },
        "geoTransform": [0.0, 5.0, 0.0, 100.0, 0.0, -5.0],
        "bands": [{"noDataValue": -9999.0}],
        "size": [20, 20],
    }
)


class GetTiffInfoTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def _write_gdalinfo_output(self, text: str) -> str:
        path = Path(self.directory.name) / "gdalinfo_output.html"
        path.write_text(text, encoding="utf-8")
        return str(path)

    def _run_with_output(self, text: str):
        output_path = self._write_gdalinfo_output(text)
        sys.modules["processing"].run = MagicMock(
            return_value={"OUTPUT": output_path}
        )
        return utils.get_tiff_info("dummy.tif")

    def test_normal_pre_wrapped_json(self):
        """正常系: <pre>...</pre>で囲まれた通常のgdalinfo出力を解析できる。"""
        info = self._run_with_output(f"<pre>{VALID_GDALINFO_JSON}</pre>")
        self.assertEqual(info["size"], [20, 20])
        self.assertEqual(info["resolution"], 5.0)
        self.assertEqual(info["nodata_value"], -9999.0)
        self.assertEqual(info["extent"], [0.0, 100.0, 0.0, 100.0])

    def test_warning_prefixed_output_still_parses(self):
        """stderrがstdoutへ混在し、JSON本体の前に警告行が入った場合でも解析できる
        （2026-11-03報告の想定原因候補: QGISのgdal:gdalinfoはstderrをstdoutへ
        統合するため、GDAL側の警告が<pre>内でJSONの前に混入し得る）。"""
        output = f"<pre>Warning 1: dummy PROJ warning\n{VALID_GDALINFO_JSON}\n</pre>"
        info = self._run_with_output(output)
        self.assertEqual(info["size"], [20, 20])

    def test_empty_output_raises_clear_runtime_error(self):
        """空出力: gdalinfoが何も書き出さなかった場合（ファイルを開けなかった場合
        の典型的な症状）、生のJSONDecodeErrorではなく原因の分かるRuntimeErrorに
        なる。"""
        with self.assertRaisesRegex(RuntimeError, "JSONが見つかりません"):
            self._run_with_output("")

    def test_malformed_json_raises_clear_runtime_error(self):
        """不正JSON: JSON本体が途中で壊れている場合、生のJSONDecodeErrorでは
        なく原因の分かるRuntimeErrorになる。"""
        broken = VALID_GDALINFO_JSON[: len(VALID_GDALINFO_JSON) // 2]
        with self.assertRaisesRegex(RuntimeError, "JSONとして解析できません"):
            self._run_with_output(f"<pre>{broken}</pre>")

    def test_gdal_execution_failure_raises_clear_runtime_error(self):
        """GDAL実行失敗: processing.run自体が例外を投げた場合（アルゴリズム
        未登録、GDALプロバイダ無効化等）、原因の分かるRuntimeErrorになる。"""
        sys.modules["processing"].run = MagicMock(
            side_effect=RuntimeError("algorithm gdal:gdalinfo not found")
        )
        with self.assertRaisesRegex(RuntimeError, "gdal:gdalinfoの実行エラー"):
            utils.get_tiff_info("dummy.tif")


if __name__ == "__main__":
    unittest.main()
