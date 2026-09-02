# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import *
import processing

from ..utils import is_resampling_needed, get_tiff_info
from . import raster_writer
from . import raster_styler
from ..constants import OUTPUT_AGGREGATE



class ProcessingThread(QThread):
    processStarted = pyqtSignal(int)
    addProgress = pyqtSignal(int)
    postMessage = pyqtSignal(str)
    processFinished = pyqtSignal(dict)
    setAbortable = pyqtSignal(bool)
    processFailed = pyqtSignal(str)

    def __init__(self, mode: str, zoning_layer_path: str, input_layer, output_path: str,
                 style_threshold: int):
        super().__init__()
        self.mode = mode
        self.zoning_layer_path = zoning_layer_path
        self.input_layer = input_layer
        self.output_path = output_path
        self.style_threshold = style_threshold

        self.abort_flag = False

    def set_abort_flag(self, flag=True):
        self.abort_flag = flag

    def run(self):
        vlayer_dict = {}

        try:
            sum_of_processes = 3
            self.processStarted.emit(sum_of_processes)

            self.addProgress.emit(1)
            self.postMessage.emit('集計用ポリゴンを準備中')

            # 任意のポリゴンで集計する場合
            if self.mode == "polygon":
                polygon_vlayer = fix_geometry(self.input_layer)
            # DEMから流域ポリゴンを生成して集計する場合
            if self.mode == "dem":
                # DEMをリサンプリング
                is_resampling = is_resampling_needed(get_tiff_info(self.input_layer))
                if is_resampling:
                    self.input_layer = raster_writer.resampling(self.input_layer, 10)
                basin_polygon = raster_writer.savearea.create_basin_polygon(
                    self.input_layer
                )
                polygon_vlayer = raster_writer.savearea.dissolve_basin_vlayer(
                    basin_polygon
                )

            self.addProgress.emit(1)
            self.postMessage.emit('ゾーン統計・ヒストグラムを集計中')

            # QGIS 3.44 native providerで集計処理を実行する
            aggregate_filepath = raster_writer.aggregate.generate(
                self.zoning_layer_path, polygon_vlayer, self.output_path
            )

            self.addProgress.emit(1)
            self.postMessage.emit('集計結果のスタイルを作成中')

            # スタイルを適用する
            vlayer = QgsVectorLayer(aggregate_filepath, OUTPUT_AGGREGATE["DISPLAY_NAME"])
            qml_filepath = raster_styler.aggregate.write_qml(self.output_path, self.style_threshold)
            vlayer.loadNamedStyle(qml_filepath)
            vlayer_dict[OUTPUT_AGGREGATE["DISPLAY_NAME"]] = vlayer
        except Exception as e:
            # エラーはまとめてキャッチして呼び出し元に報告・処理を中断
            self.processFailed.emit(str(e))
            self.abort_flag = True
            return

        self.postMessage.emit("終了処理中")
        self.processFinished.emit(vlayer_dict)



def fix_geometry(polygon_layer: QgsVectorLayer):
    """任意ポリゴンによる集計をする場合、事前にジオメトリ修復を行う関数"""
    return processing.run("native:fixgeometries", {'INPUT': polygon_layer, 'OUTPUT': 'memory:'})['OUTPUT']
