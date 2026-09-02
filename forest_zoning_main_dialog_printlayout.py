# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

# QGIS-API
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import *

from . import processes
from .constants import (
    OUTPUT_ZONING,
    OUTPUT_AGGREGATE,
)


class ForestZoningMainDialogPrintlayout:
    """
    メイン画面の「印刷」タブの処理を実装するクラス
    """

    def __init__(self, main):
        self.main = main
        self.init_printlayout_ui()

    def init_printlayout_ui(self):
        # connect signals
        self.main.zoningPrintlayoutSetLayersButton.clicked.connect(
            self.set_zoning_layer_printlayout_combobox
        )
        self.main.aggregatePrintlayoutSetLayersButton.clicked.connect(
            self.set_aggregate_layer_printlayout_combobox
        )
        self.main.createZoningPrintlayoutPushButton.clicked.connect(
            lambda: self.run_printlayout("zoning")
        )
        self.main.createAggregatePrintlayoutPushButton.clicked.connect(
            lambda: self.run_printlayout("aggregate")
        )

        self.main.printlayoutBackgroundLayerCombobox.setFilters(
            QgsMapLayerProxyModel.RasterLayer
        )
        self.main.printlayoutZoningLayerCombobox.setFilters(
            QgsMapLayerProxyModel.RasterLayer
        )
        self.main.printlayoutAggregateLayerCombobox.setFilters(
            QgsMapLayerProxyModel.VectorLayer
        )

        self.main.printlayoutBackgroundLayerCombobox.layerChanged.connect(
            self.refresh_create_zoning_printlayout_ui
        )
        self.main.printlayoutBackgroundLayerCombobox.layerChanged.connect(
            self.refresh_create_aggregate_printlayout_ui
        )
        self.main.printlayoutZoningLayerCombobox.layerChanged.connect(
            self.refresh_create_zoning_printlayout_ui
        )
        self.main.printlayoutAggregateLayerCombobox.layerChanged.connect(
            self.refresh_create_aggregate_printlayout_ui
        )
        self.refresh_create_zoning_printlayout_ui()
        self.refresh_create_aggregate_printlayout_ui()

    def refresh_create_zoning_printlayout_ui(self):
        error_texts = self.get_create_zoning_printlayout_error()
        has_no_error = len(error_texts) == 0
        self.main.createZoningPrintlayoutErrorLabel.setText("\n".join(error_texts))
        self.main.createZoningPrintlayoutPushButton.setEnabled(has_no_error)

    def get_create_zoning_printlayout_error(self) -> list:
        error_texts = []
        if self.main.printlayoutBackgroundLayerCombobox.currentLayer() is None:
            error_texts.append("背景レイヤを指定してください")
        if self.main.printlayoutZoningLayerCombobox.currentLayer() is None:
            error_texts.append("ゾーニング図を指定してください")
        return error_texts

    def refresh_create_aggregate_printlayout_ui(self):
        error_texts = self.get_create_aggregate_printlayout_error()
        has_no_error = len(error_texts) == 0
        self.main.createAggregatePrintlayoutErrorLabel.setText("\n".join(error_texts))
        self.main.createAggregatePrintlayoutPushButton.setEnabled(has_no_error)

    def get_create_aggregate_printlayout_error(self) -> list:
        error_texts = []
        if self.main.printlayoutBackgroundLayerCombobox.currentLayer() is None:
            error_texts.append("背景レイヤを指定してください")
        if self.main.printlayoutAggregateLayerCombobox.currentLayer() is None:
            error_texts.append("ゾーン統計量を指定してください")
        return error_texts

    def set_zoning_layer_printlayout_combobox(self):
        zoning_rlayers = QgsProject.instance().mapLayersByName(
            OUTPUT_ZONING.get("DISPLAY_NAME")
        )
        if len(zoning_rlayers) > 0:
            zoning_layer = zoning_rlayers[0]
            self.main.printlayoutZoningLayerCombobox.setLayer(zoning_layer)
        else:
            QMessageBox.information(self.main, "エラー", "ゾーニング図を作成してください。")
            return

    def set_aggregate_layer_printlayout_combobox(self):
        aggregate_layers = QgsProject.instance().mapLayersByName(
            OUTPUT_AGGREGATE.get("DISPLAY_NAME")
        )
        if len(aggregate_layers) > 0:
            aggregate_layer = aggregate_layers[0]
            self.main.printlayoutAggregateLayerCombobox.setLayer(aggregate_layer)
        else:
            QMessageBox.information(self.main, "エラー", "ゾーン統計量を作成してください。")
            return

    def run_printlayout(self, target_name):
        project = QgsProject.instance()
        manager = project.layoutManager()
        printlayout_list = [layout.name() for layout in manager.printLayouts()]
        background_layer = self.main.printlayoutBackgroundLayerCombobox.currentLayer()

        if target_name == "zoning":
            target_layer = self.main.printlayoutZoningLayerCombobox.currentLayer()
            printlayout_name = "ゾーニング図"
        else:
            target_layer = self.main.printlayoutAggregateLayerCombobox.currentLayer()
            printlayout_name = "ゾーン統計量"

        if printlayout_name in printlayout_list:
            if QMessageBox.No == QMessageBox.question(
                self.main,
                "上書き確認",
                f'出力先フォルダに"{printlayout_name}"のレイアウトが存在します、上書きしますか？',
                QMessageBox.Yes,
                QMessageBox.No,
            ):
                QMessageBox.information(self.main, "処理中断", "処理を中断しました。")
                return
            project.layoutManager().removeLayout(manager.layoutByName(printlayout_name))

        processes.printlayout.create_printlayout.generate(
            target_name, background_layer, target_layer
        )
        self.main.hide()
