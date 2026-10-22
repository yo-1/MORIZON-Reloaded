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
        from qgis.PyQt.QtCore import Qt, QEvent
        from qgis.PyQt.QtGui import QPainter
        from qgis.PyQt.QtWidgets import QDialog, QFileDialog, QMessageBox, QSpinBox
        from qgis.core import (QgsContrastEnhancement, QgsLayoutItem,
                               QgsMapLayer, QgsMapLayerProxyModel,
                               QgsRasterMinMaxOrigin, QgsUnitTypes)

        enum_paths = (
            "QSpinBox.ButtonSymbols.NoButtons",
            "QFileDialog.Option.ShowDirsOnly",
            "QMessageBox.Icon.Warning",
            "QMessageBox.ButtonRole.AcceptRole",
            "QMessageBox.ButtonRole.ActionRole",
            "QMessageBox.StandardButton.Yes",
            "QMessageBox.StandardButton.No",
            "QMessageBox.StandardButton.Cancel",
            "QDialog.DialogCode.Accepted",
            "QEvent.Type.DeferredDelete",
            "QPainter.CompositionMode.CompositionMode_Multiply",
            "QgsMapLayer.LayerType.RasterLayer",
            "QgsMapLayerProxyModel.Filter.RasterLayer",
            "QgsMapLayerProxyModel.Filter.VectorLayer",
            "Qgis.MessageLevel.Critical",
            "Qgis.MessageLevel.Warning",
            "Qgis.MessageLevel.Info",
            "Qt.Key.Key_Escape",
            "Qt.AspectRatioMode.KeepAspectRatio",
            "Qt.TransformationMode.SmoothTransformation",
            "Qt.AlignmentFlag.AlignCenter",
            "Qt.WindowType.WindowCloseButtonHint",
            "Qt.WindowType.WindowStaysOnTopHint",
            "QgsContrastEnhancement.ContrastEnhancementAlgorithm.StretchToMinimumMaximum",
            "QgsLayoutItem.ReferencePoint.Middle",
            "Qgis.RasterBandStatistic.Max",
            "Qgis.RasterBandStatistic.Min",
            "QgsRasterMinMaxOrigin.Limits.MinMax",
            "QgsUnitTypes.DistanceUnit.DistanceKilometers",
            "QgsUnitTypes.LayoutUnit.LayoutMillimeters",
        )
        scope = {
            cls.__name__: cls for cls in (
                QSpinBox, QFileDialog, QMessageBox, QDialog, QEvent, QPainter,
                QgsMapLayer, QgsMapLayerProxyModel, QgsContrastEnhancement,
                QgsLayoutItem, QgsRasterMinMaxOrigin, QgsUnitTypes, Qgis,
            )
        }
        scope["Qt"] = Qt
        for dotted in enum_paths:
            root, *attributes = dotted.split(".")
            value = scope[root]
            for attribute in attributes:
                value = getattr(value, attribute)
        print(f"QGIS {Qgis.QGIS_VERSION}: imported {len(paths)} plugin modules")
        print(f"Resolved {len(enum_paths)} Qt/QGIS enum paths")
    app.exitQgis()


if __name__ == "__main__":
    main()
