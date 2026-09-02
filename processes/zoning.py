# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

import os
import json

from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import *

from . import raster_writer
from . import raster_styler
from ..constants import OUTPUT_ZONING, OUTPUT_ZONING_THRESHOLDS_JSON


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
        output_dir: str,
    ):
        super().__init__()
        self.input_layers_dict = input_layers_dict
        self.input_thresholds_dict = input_thresholds_dict
        self.output_dir = output_dir

        self.abort_flag = False

    def set_abort_flag(self, flag=True):
        self.abort_flag = flag

    def run(self):
        """
        「ゾーニング」処理を実行する
        """

        # 処理に成功したレイヤーの名前とインスタンスを保持する辞書
        output_rlayers_dict = {}

        try:
            sum_of_processes = 1
            self.processStarted.emit(sum_of_processes)

            self.addProgress.emit(1)
            self.postMessage.emit("ゾーニングを計算中")

            zoning_filepath = raster_writer.zoning.generate(
                self.input_layers_dict["profit"],
                self.input_thresholds_dict["profit"],
                self.input_layers_dict["risk"],
                self.input_thresholds_dict["risk"],
                self.output_dir,
            )

            if os.path.basename(zoning_filepath) != (
                OUTPUT_ZONING["FILE_NAME"] + "." + OUTPUT_ZONING["EXTENSION"]
            ):
                self.postMessage.emit(
                    "既存のゾーニング図を保持し、"
                    f"{os.path.basename(zoning_filepath)} として新規保存しました"
                )

            # ラスターレイヤーのインスタンスを生成しスタイル適用
            rlayer = QgsRasterLayer(zoning_filepath, OUTPUT_ZONING["DISPLAY_NAME"])
            qml_filepath = raster_styler.zoning.write_qml(self.output_dir)
            rlayer.loadNamedStyle(qml_filepath)

            output_rlayers_dict[OUTPUT_ZONING["DISPLAY_NAME"]] = rlayer

        except Exception as e:
            # エラーはまとめてキャッチして呼び出し元に報告・処理を中断
            self.processFailed.emit(str(e))
            self.abort_flag = True
            self.processFinished.emit(output_rlayers_dict)
            return

        # zoning_vN.tif の場合、対応する thresholds_vN.json を保存する。
        zoning_stem = os.path.splitext(os.path.basename(zoning_filepath))[0]
        suffix = zoning_stem[len(OUTPUT_ZONING["FILE_NAME"]):]
        thresholds_name = (
            OUTPUT_ZONING_THRESHOLDS_JSON["FILE_NAME"]
            + suffix
            + "."
            + OUTPUT_ZONING_THRESHOLDS_JSON["EXTENSION"]
        )
        with open(
            os.path.join(self.output_dir, thresholds_name),
            mode="wt",
        ) as f:
            json.dump(self.input_thresholds_dict, f, ensure_ascii=False, indent=2)

        self.postMessage.emit("終了処理中")

        # 本当はここでプロジェクトにレイヤーを追加したい
        # しかし別スレッドでプロジェクトに追加されたレイヤーはUIで認識できない
        # なのでメインスレッドでレイヤーを追加するため、処理結果をメインスレッドに渡す
        self.processFinished.emit(output_rlayers_dict)
