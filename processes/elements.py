# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

import os
# QGIS-API
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import *

from . import raster_writer
from . import raster_styler
from ..utils import get_tiff_info, is_resampling_needed
from ..constants import (
    OUTPUT_COST,
    OUTPUT_DISTANCE,
    OUTPUT_SAVEAREA,
    OUTPUT_SITEIDX_HINOKI,
    OUTPUT_SITEIDX_KARAMATSU,
    OUTPUT_SITEIDX_SUGI,
    OUTPUT_SHC,
    OUTPUT_SLOPE
)


class ProcessingThread(QThread):
    processStarted = pyqtSignal(int)
    addProgress = pyqtSignal(int)
    postMessage = pyqtSignal(str)
    processFinished = pyqtSignal(dict)
    setAbortable = pyqtSignal(bool)
    processFailed = pyqtSignal(str)

    def __init__(self, input_files_dict: dict, target_elements_dict: dict, output_dir: str):
        super().__init__()
        self.input_files_dict = input_files_dict
        self.target_elements_dict = target_elements_dict
        self.output_dir = output_dir

        self.abort_flag = False

    def set_abort_flag(self, flag=True):
        self.abort_flag = flag

    def run(self):
        """
        「要素計算」処理を実行する
        最大6種類8ラスターが生成され、1ラスターにつき2レイヤーがプロジェクトに追加される

        Args:
            input_files_dict (dict): 入力ファイルに関するUIの入力状態をまとめた辞書
            target_elements_dict (dict): どの要素が処理対象かまとめた辞書 - {レイヤー名: bool}
            output_dir (str): ファイル出力先
        """

        # 処理に成功したレイヤーの名前とインスタンスを保持する辞書
        output_rlayers_dict = {}

        try:
            is_resampling = is_resampling_needed(
                get_tiff_info(self.input_files_dict["dem"]))

            sum_of_processes = len(list(filter(
                lambda val: val, self.target_elements_dict.values()))) + int(is_resampling)
            self.processStarted.emit(sum_of_processes)
            progress_counter = 0

            # 必要ならDEMをリサンプリング
            dem_for_processes = self.input_files_dict["dem"]
            if is_resampling:
                self.addProgress.emit(1)
                progress_counter += 1
                self.postMessage.emit('DEMをリサンプリング中')
                dem_for_processes = raster_writer.resampling(
                    self.input_files_dict["dem"], 10)

                if self.abort_flag:
                    self.processFinished.emit({})
                    return

            if self.target_elements_dict["siteidx"]:
                self.postMessage.emit('地位指数を計算中')
                self.setAbortable.emit(sum_of_processes - progress_counter > 1)
                self.addProgress.emit(1)
                progress_counter += 1

                siteidx_filepaths = raster_writer.siteidx.generate(dem_for_processes,
                                                                   self.input_files_dict["npp"],
                                                                   self.input_files_dict["srad"],
                                                                   self.input_files_dict["vtex"],
                                                                   self.output_dir)
                display_names = [
                    OUTPUT_SITEIDX_SUGI["DISPLAY_NAME"],
                    OUTPUT_SITEIDX_HINOKI["DISPLAY_NAME"],
                    OUTPUT_SITEIDX_KARAMATSU["DISPLAY_NAME"]
                ]
                siteidx_suffixes = ["sugi", "hinoki", "karamatsu"]

                for idx, path in enumerate(siteidx_filepaths):
                    siteidx_rawdata_qml_filepath = raster_styler.siteidx.write_rawdata_qml(
                        path, wood_type=siteidx_suffixes[idx])
                    siteidx_scoring_qml_filepath = raster_styler.siteidx.write_scoring_qml(
                        path)
                    siteidx_rawdata_rlayer = QgsRasterLayer(path,
                                                            display_names[idx])
                    siteidx_scoring_rlayer = QgsRasterLayer(path,
                                                            display_names[idx] + "[スコアリング]")
                    siteidx_rawdata_rlayer.loadNamedStyle(
                        siteidx_rawdata_qml_filepath)
                    siteidx_scoring_rlayer.loadNamedStyle(
                        siteidx_scoring_qml_filepath)
                    output_rlayers_dict[display_names[idx]] = [
                        siteidx_rawdata_rlayer, siteidx_scoring_rlayer]

                if self.abort_flag:
                    self.processFinished.emit(output_rlayers_dict)
                    return

            if self.target_elements_dict["cost"]:
                self.postMessage.emit(f'{OUTPUT_COST["DISPLAY_NAME"]}を計算中')
                self.setAbortable.emit(sum_of_processes - progress_counter > 1)
                self.addProgress.emit(1)
                progress_counter += 1

                cost_filepath = raster_writer.cost.generate(dem_for_processes,
                                                            self.input_files_dict["costcsv"],
                                                            self.output_dir)
                cost_rawdata_qml_filepath = raster_styler.cost.write_rawdata_qml(self.input_files_dict["costcsv"],
                                                                                 self.output_dir)
                cost_scoring_qml_filepath = raster_styler.cost.write_scoring_qml(cost_filepath,
                                                                                 self.output_dir)
                cost_rawdata_rlayer = QgsRasterLayer(cost_filepath,
                                                     OUTPUT_COST["DISPLAY_NAME"])
                cost_scoring_rlayer = QgsRasterLayer(cost_filepath,
                                                     OUTPUT_COST["DISPLAY_NAME"] + "[スコアリング]")
                cost_rawdata_rlayer.loadNamedStyle(cost_rawdata_qml_filepath)
                cost_scoring_rlayer.loadNamedStyle(cost_scoring_qml_filepath)

                output_rlayers_dict[OUTPUT_COST["DISPLAY_NAME"]] = [
                    cost_rawdata_rlayer, cost_scoring_rlayer]

                if self.abort_flag:
                    self.processFinished.emit(output_rlayers_dict)
                    return

            if self.target_elements_dict["distance"]:
                self.postMessage.emit(f'{OUTPUT_DISTANCE["DISPLAY_NAME"]}を計算中')
                self.setAbortable.emit(sum_of_processes - progress_counter > 1)
                self.addProgress.emit(1)
                progress_counter += 1

                distance_filepath = raster_writer.distance.generate(dem_for_processes,
                                                                    self.input_files_dict["network"],
                                                                    self.output_dir)
                distance_rawdata_qml_filepath = raster_styler.distance.write_rawdata_qml(
                    self.output_dir)
                distance_scoring_qml_filepath = raster_styler.distance.write_scoring_qml(distance_filepath,
                                                                                         self.output_dir)
                distance_rawdata_rlayer = QgsRasterLayer(distance_filepath,
                                                         OUTPUT_DISTANCE["DISPLAY_NAME"])
                distance_scoring_rlayer = QgsRasterLayer(distance_filepath,
                                                         OUTPUT_DISTANCE["DISPLAY_NAME"] + "[スコアリング]")
                distance_rawdata_rlayer.loadNamedStyle(
                    distance_rawdata_qml_filepath)
                distance_scoring_rlayer.loadNamedStyle(
                    distance_scoring_qml_filepath)
                output_rlayers_dict[OUTPUT_DISTANCE["DISPLAY_NAME"]] = [
                    distance_rawdata_rlayer, distance_scoring_rlayer]

                if self.abort_flag:
                    self.processFinished.emit(output_rlayers_dict)
                    return

            if self.target_elements_dict["shc"]:
                self.postMessage.emit(f'{OUTPUT_SHC["DISPLAY_NAME"]}を計算中')
                self.setAbortable.emit(sum_of_processes - progress_counter > 1)
                self.addProgress.emit(1)
                progress_counter += 1

                shc_filepath = raster_writer.shc.generate(dem_for_processes,
                                                          self.output_dir)
                shc_rawdata_qml_filepath = raster_styler.shc.write_rawdata_qml(shc_filepath,
                                                                               self.output_dir)
                shc_scoring_qml_filepath = raster_styler.shc.write_scoring_qml(shc_filepath,
                                                                               self.output_dir)
                shc_rawdata_rlayer = QgsRasterLayer(shc_filepath,
                                                    OUTPUT_SHC["DISPLAY_NAME"])
                shc_scoring_rlayer = QgsRasterLayer(shc_filepath,
                                                    OUTPUT_SHC["DISPLAY_NAME"] + "[スコアリング]")
                shc_rawdata_rlayer.loadNamedStyle(shc_rawdata_qml_filepath)
                shc_scoring_rlayer.loadNamedStyle(shc_scoring_qml_filepath)
                output_rlayers_dict[OUTPUT_SHC["DISPLAY_NAME"]] = [
                    shc_rawdata_rlayer, shc_scoring_rlayer]

                if self.abort_flag:
                    self.processFinished.emit(output_rlayers_dict)
                    return

            if self.target_elements_dict["slope"]:
                self.postMessage.emit(f'{OUTPUT_SLOPE["DISPLAY_NAME"]}を計算中')
                self.setAbortable.emit(sum_of_processes - progress_counter > 1)
                self.addProgress.emit(1)
                progress_counter += 1

                slope_filepath = raster_writer.slope.generate(dem_for_processes,
                                                              self.output_dir)
                slope_rawdata_qml_filepath = raster_styler.slope.write_rawdata_qml(
                    self.output_dir)
                slope_scoring_qml_filepath = raster_styler.slope.write_scoring_qml(
                    self.output_dir)
                slope_rawdata_rlayer = QgsRasterLayer(slope_filepath,
                                                      OUTPUT_SLOPE["DISPLAY_NAME"])
                slope_scoring_rlayer = QgsRasterLayer(slope_filepath,
                                                      OUTPUT_SLOPE["DISPLAY_NAME"] + "[スコアリング]")
                slope_rawdata_rlayer.loadNamedStyle(slope_rawdata_qml_filepath)
                slope_scoring_rlayer.loadNamedStyle(slope_scoring_qml_filepath)
                output_rlayers_dict[OUTPUT_SLOPE["DISPLAY_NAME"]] = [
                    slope_rawdata_rlayer, slope_scoring_rlayer]

                if self.abort_flag:
                    self.processFinished.emit(output_rlayers_dict)
                    return

            if self.target_elements_dict["savearea"]:
                self.postMessage.emit(f'{OUTPUT_SAVEAREA["DISPLAY_NAME"]}を計算中')
                self.setAbortable.emit(sum_of_processes - progress_counter > 1)
                self.addProgress.emit(1)
                progress_counter += 1

                savearea_filepath = raster_writer.savearea.generate(
                    dem_for_processes,
                    self.input_files_dict["building"],
                    self.output_dir,
                    self.input_files_dict.get("building_crs_override_authid")
                )
                if os.path.basename(savearea_filepath) != OUTPUT_SAVEAREA["FILE_NAME"] + ".tif":
                    self.postMessage.emit(
                        "既存の保全対象流域ファイルがWindowsで使用中のため、"
                        f"{os.path.basename(savearea_filepath)} として新規保存しました"
                    )
                savearea_rawdata_qml_filepath = raster_styler.savearea.write_rawdata_qml(
                    self.output_dir)
                savearea_scoring_qml_filepath = raster_styler.savearea.write_scoring_qml(
                    self.output_dir)
                savearea_rawdata_rlayer = QgsRasterLayer(savearea_filepath,
                                                         OUTPUT_SAVEAREA["DISPLAY_NAME"])
                savearea_scoring_rlayer = QgsRasterLayer(savearea_filepath,
                                                         OUTPUT_SAVEAREA["DISPLAY_NAME"] + "[スコアリング]")
                savearea_rawdata_rlayer.loadNamedStyle(
                    savearea_rawdata_qml_filepath)
                savearea_scoring_rlayer.loadNamedStyle(
                    savearea_scoring_qml_filepath)
                output_rlayers_dict[OUTPUT_SAVEAREA["DISPLAY_NAME"]] = [
                    savearea_rawdata_rlayer, savearea_scoring_rlayer]
        except Exception as e:
            # エラーはまとめてキャッチして呼び出し元に報告・処理を中断
            self.processFailed.emit(str(e))
            self.abort_flag = True
            self.processFinished.emit(output_rlayers_dict)
            return

        self.postMessage.emit('終了処理中')

        # 本当はここでプロジェクトにレイヤーを追加したい
        # しかし別スレッドでプロジェクトに追加されたレイヤーはUIで認識できない
        # なのでメインスレッドでレイヤーを追加するため、処理結果をメインスレッドに渡す
        self.processFinished.emit(output_rlayers_dict)
