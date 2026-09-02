# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

import os
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import *

from . import raster_writer
from . import raster_styler
from ..constants import (
    OUTPUT_PROFIT,
    OUTPUT_RISK,
)


class ProcessingThread(QThread):
    processStarted = pyqtSignal(int)
    addProgress = pyqtSignal(int)
    postMessage = pyqtSignal(str)
    processFinished = pyqtSignal(dict)
    setAbortable = pyqtSignal(bool)
    processFailed = pyqtSignal(str)

    def __init__(
        self,
        input_layers_dict: dict,
        input_thresholds_dict: dict,
        target_scores_dict: dict,
        output_dir: str,
    ):
        super().__init__()
        self.input_layers_dict = input_layers_dict
        self.input_thresholds_dict = input_thresholds_dict
        self.target_scores_dict = target_scores_dict
        self.output_dir = output_dir

        self.abort_flag = False

    def set_abort_flag(self, flag=True):
        self.abort_flag = flag

    def run(self):
        """
        「スコアリング」処理を実行する
        """

        # 処理に成功したレイヤーの名前とインスタンスを保持する辞書
        output_rlayers_dict = {}

        try:
            sum_of_processes = len(
                list(filter(lambda val: val, self.target_scores_dict.values()))
            )
            self.processStarted.emit(sum_of_processes)

            if self.target_scores_dict["profit"]:
                self.addProgress.emit(1)
                self.postMessage.emit("収益性を計算中")

                profit_filepath = raster_writer.profit.generate(
                    self.input_layers_dict["siteidx"],
                    self.input_thresholds_dict["siteidx"],
                    self.input_layers_dict["cost"],
                    self.input_thresholds_dict["cost"],
                    self.input_layers_dict["distance"],
                    self.input_thresholds_dict["distance"],
                    self.output_dir,
                )
                if os.path.basename(profit_filepath) != OUTPUT_PROFIT["FILE_NAME"] + ".tif":
                    self.postMessage.emit(
                        "既存の収益性ファイルがWindowsで使用中のため、"
                        f"{os.path.basename(profit_filepath)} として新規保存しました"
                    )
                rlayer = QgsRasterLayer(profit_filepath, OUTPUT_PROFIT["DISPLAY_NAME"])
                qml_filepath = raster_styler.profit.write_qml(
                    profit_filepath, self.output_dir
                )
                rlayer.loadNamedStyle(qml_filepath)
                output_rlayers_dict[OUTPUT_PROFIT["DISPLAY_NAME"]] = rlayer

                if self.abort_flag:
                    self.processFinished.emit(output_rlayers_dict)
                    return

            if self.target_scores_dict["risk"]:
                self.addProgress.emit(1)
                self.setAbortable.emit(False)
                self.postMessage.emit("リスクを計算中")

                risk_filepath = raster_writer.risk.generate(
                    self.input_layers_dict["slope"],
                    self.input_thresholds_dict["slope"],
                    self.input_layers_dict["shc"],
                    self.input_thresholds_dict["shc"],
                    self.input_layers_dict["savearea"],
                    self.output_dir,
                )
                if os.path.basename(risk_filepath) != OUTPUT_RISK["FILE_NAME"] + ".tif":
                    self.postMessage.emit(
                        "既存の災害リスクファイルがWindowsで使用中のため、"
                        f"{os.path.basename(risk_filepath)} として新規保存しました"
                    )
                rlayer = QgsRasterLayer(risk_filepath, OUTPUT_RISK["DISPLAY_NAME"])
                qml_filepath = raster_styler.risk.write_qml(
                    risk_filepath, self.output_dir
                )
                rlayer.loadNamedStyle(qml_filepath)
                output_rlayers_dict[OUTPUT_RISK["DISPLAY_NAME"]] = rlayer

        except Exception as e:
            # エラーはまとめてキャッチして呼び出し元に報告・処理を中断
            self.processFailed.emit(str(e))
            self.abort_flag = True
            self.processFinished.emit(output_rlayers_dict)
            return

        self.postMessage.emit("終了処理中")

        # 本当はここでプロジェクトにレイヤーを追加したい
        # しかし別スレッドでプロジェクトに追加されたレイヤーはUIで認識できない
        # なのでメインスレッドでレイヤーを追加するため、処理結果をメインスレッドに渡す
        self.processFinished.emit(output_rlayers_dict)
