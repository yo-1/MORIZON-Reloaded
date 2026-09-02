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
from qgis.utils import iface

from .processes.raster_styler import (
    write_qml_deviding_by_threshold,
)
from . import processes
from . import utils
from .progress_dialog import ProgressDialog
from .constants import (
    OUTPUT_PROFIT,
    OUTPUT_RISK,
    OUTPUT_ZONING,
    OUTPUT_ZONING_THRESHOLDS_JSON,
    SCORING_COLORS_PROFIT,
    SCORING_COLORS_RISK,
)


class ForestZoningMainDialogZoning:
    """
    メイン画面の「ゾーニング」タブの処理を実装するクラス
    """

    def __init__(self, main):
        self.main = main
        self.init_zoning_ui()

    def init_zoning_ui(self):
        """
        初回にのみ発火してUIと関数の紐付けなどの初期化処理を行う関数
        """
        self.main.zoningRunButton.clicked.connect(self.run_zoning)
        self.main.zoningSetLayersButton.clicked.connect(self.set_zoning_layer_combobox)
        self.main.zoningProfitUpdateButton.clicked.connect(
            lambda: self.set_zoning_raster_style("profit")
        )
        self.main.zoningRiskUpdateButton.clicked.connect(
            lambda: self.set_zoning_raster_style("risk")
        )

        # ラスターレイヤーだけを選択可能に
        for combobox in (
            self.main.zoningProfitLayerCombobox,
            self.main.zoningRiskLayerCombobox,
        ):
            combobox.setFilters(QgsMapLayerProxyModel.RasterLayer)

        # UI入力時にステート更新
        self.main.zoningProfitLayerCombobox.layerChanged.connect(
            self.refresh_zoning_ui
        )  # nopep8
        self.main.zoningProfitLayerCombobox.layerChanged.connect(
            self.set_zoning_thresholds
        )  # nopep8
        self.main.zoningRiskLayerCombobox.layerChanged.connect(
            self.refresh_zoning_ui
        )  # nopep8
        self.main.zoningRiskLayerCombobox.layerChanged.connect(
            self.set_zoning_thresholds
        )  # nopep8
        self.main.zoningOutputDirFileWidget.fileChanged.connect(
            self.refresh_zoning_ui
        )  # nopep8

        self.refresh_zoning_ui()
        self.set_zoning_thresholds()

    def refresh_zoning_ui(self):
        """
        UIの変更の都度発火してUIの状態を更新する関数
        """

        error_texts = self.get_zoning_error_texts()
        has_no_error = len(error_texts) == 0
        self.main.zoningErrorLabel.setText("\n".join(error_texts))
        self.main.zoningRunButton.setEnabled(has_no_error)

        for combobox, reload_button in (
            (self.main.zoningProfitLayerCombobox, self.main.zoningProfitUpdateButton),
            (self.main.zoningRiskLayerCombobox, self.main.zoningRiskUpdateButton),
        ):
            combobox_has_layer = combobox.currentLayer() is not None
            reload_button.setEnabled(combobox_has_layer)

    def get_zoning_error_texts(self) -> list:
        """
        UIの入力をチェックしてエラーを文字列の配列で返す
        要素数0=エラー無し
        Returns:
            list: 要素数が0以上のstrの配列
        """
        error_texts = []
        for name, combobox in (
            (OUTPUT_PROFIT["DISPLAY_NAME"], self.main.zoningProfitLayerCombobox),
            (OUTPUT_RISK["DISPLAY_NAME"], self.main.zoningRiskLayerCombobox),
        ):
            if combobox.currentLayer() is None:
                error_texts.append(f"{name}ラスターを指定してください")
                continue

            if not utils.is_valid_scoring_layer(combobox.currentLayer()):
                error_texts.append(f"有効な{name}ラスターを指定してください")
                continue

        if self.main.zoningOutputDirFileWidget.filePath() == "":
            error_texts.append("出力先フォルダを指定してください")

        return error_texts

    def set_zoning_layer_combobox(self):
        """収益性・災害リスクをQGIS 3.44で確実に自動設定する。

        探索順:
        1. プロジェクトに読込済みの shuekisei / saigairisk
        2. スコアリング出力先・現在の出力先
        3. YOUSO の兄弟 ZONING
        4. プロジェクト内ラスタのフォルダ / 兄弟 ZONING

        Windowsロック対策で _vN がある場合は最大世代を優先する。
        見つかったファイルが未読込ならQGISへ自動ロードする。
        """
        project = QgsProject.instance()

        def source_path(layer):
            if layer is None:
                return ""
            for getter in (
                lambda: layer.source(),
                lambda: layer.dataProvider().dataSourceUri(),
            ):
                try:
                    value = getter()
                    if value:
                        return value.split("|", 1)[0]
                except Exception:
                    pass
            return ""

        def generation(path, wanted):
            base = os.path.splitext(os.path.basename(path))[0].lower()
            wanted = wanted.lower()
            if base == wanted:
                return 0
            import re
            m = re.fullmatch(re.escape(wanted) + r"_v([0-9]+)", base, re.I)
            return int(m.group(1)) if m else None

        def raster_layers():
            return [
                lyr for lyr in project.mapLayers().values()
                if lyr is not None and lyr.type() == QgsMapLayer.RasterLayer
            ]

        def add_dir(d, dirs):
            if not d:
                return
            try:
                d = os.path.abspath(d)
            except Exception:
                return
            if os.path.isdir(d) and d not in dirs:
                dirs.append(d)

        # 探索対象フォルダを広く収集する。
        dirs = []

        try:
            add_dir(self.main.zoningOutputDirFileWidget.filePath(), dirs)
        except Exception:
            pass

        try:
            add_dir(self.main.scoringOutputDirFileWidget.filePath(), dirs)
        except Exception:
            pass

        try:
            elements_dir = self.main.elementsOutputDirFileWidget.filePath()
            if elements_dir:
                add_dir(elements_dir, dirs)
                if os.path.basename(os.path.abspath(elements_dir)).lower() == "youso":
                    add_dir(os.path.join(os.path.dirname(os.path.abspath(elements_dir)), "ZONING"), dirs)
        except Exception:
            pass

        for lyr in raster_layers():
            path = source_path(lyr)
            if not path:
                continue
            d = os.path.dirname(os.path.abspath(path))
            add_dir(d, dirs)

            # YOUSOから兄弟ZONINGを推定
            if os.path.basename(d).lower() == "youso":
                add_dir(os.path.join(os.path.dirname(d), "ZONING"), dirs)

            # データセット直下にZONINGがあれば候補化
            add_dir(os.path.join(os.path.dirname(d), "ZONING"), dirs)

        def best_loaded(wanted):
            candidates = []
            for lyr in raster_layers():
                path = source_path(lyr)
                if not path:
                    continue
                gen = generation(path, wanted)
                if gen is not None:
                    candidates.append((gen, lyr))
            if not candidates:
                return None
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]

        def best_file(wanted):
            candidates = []
            for d in dirs:
                try:
                    names = os.listdir(d)
                except OSError:
                    continue
                for name in names:
                    if not name.lower().endswith((".tif", ".tiff")):
                        continue
                    path = os.path.join(d, name)
                    gen = generation(path, wanted)
                    if gen is not None:
                        candidates.append((gen, path))
            if not candidates:
                return None
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]

        def resolve(wanted, display_name):
            lyr = best_loaded(wanted)
            if lyr is not None:
                return lyr

            path = best_file(wanted)
            if not path:
                return None

            lyr = QgsRasterLayer(path, display_name)
            if not lyr.isValid():
                return None
            project.addMapLayer(lyr, True)
            return lyr

        profit = resolve(OUTPUT_PROFIT["FILE_NAME"], OUTPUT_PROFIT["DISPLAY_NAME"])
        risk = resolve(OUTPUT_RISK["FILE_NAME"], OUTPUT_RISK["DISPLAY_NAME"])

        blockers = [
            QSignalBlocker(self.main.zoningProfitLayerCombobox),
            QSignalBlocker(self.main.zoningRiskLayerCombobox),
        ]
        try:
            self.main.zoningProfitLayerCombobox.setLayer(profit)
            self.main.zoningRiskLayerCombobox.setLayer(risk)
        finally:
            blockers.clear()

        # 入力結果の存在するフォルダをゾーニング出力先に自動設定。
        for lyr in (profit, risk):
            path = source_path(lyr)
            if path:
                output_dir = os.path.dirname(os.path.abspath(path))
                try:
                    os.makedirs(output_dir, exist_ok=True)
                    self.main.zoningOutputDirFileWidget.setFilePath(output_dir)
                    if hasattr(self.main.zoningOutputDirFileWidget, "setDefaultRoot"):
                        self.main.zoningOutputDirFileWidget.setDefaultRoot(output_dir)
                except Exception:
                    pass
                break

        # ゾーニング閾値(4/6等)は入力ラスターから再設定する。
        self.set_zoning_thresholds()

        # 自動ロードされた収益性・災害リスクはQGIS既定のグレースケールに
        # なることがあるため、現在のしきい値で色表示を再適用する。
        try:
            if profit is not None:
                self.set_zoning_raster_style("profit")
            if risk is not None:
                self.set_zoning_raster_style("risk")
        except Exception:
            pass

        self.refresh_zoning_ui()

    def set_zoning_thresholds(self):
        """
        収益性・災害リスクのしきい値を、入力ラスターの値域から計算してセットする
        """
        for combobox, spinbox in (
            (self.main.zoningProfitLayerCombobox, self.main.zoningProfitSpinbox),
            (self.main.zoningRiskLayerCombobox, self.main.zoningRiskSpinbox),
        ):
            spinbox.setValue(0)  # 初期化
            if combobox.currentLayer() is not None:
                if utils.is_valid_scoring_layer(combobox.currentLayer()):
                    threshold = utils.get_initial_thresholds(
                        combobox.currentLayer(), classes_count=2
                    )[0]
                    spinbox.setValue(int(round(float(threshold))))

    def set_zoning_raster_style(self, layer_name: str):
        if layer_name == "profit":
            qml_filepath = write_qml_deviding_by_threshold(
                self.main.zoningProfitSpinbox.value(),
                SCORING_COLORS_PROFIT[0],
                SCORING_COLORS_PROFIT[1],
            )
            target_layer = self.main.zoningProfitLayerCombobox.currentLayer()
            opacity = 0.5
        elif layer_name == "risk":
            qml_filepath = write_qml_deviding_by_threshold(
                self.main.zoningRiskSpinbox.value(),
                SCORING_COLORS_RISK[0],
                SCORING_COLORS_RISK[1],
            )
            target_layer = self.main.zoningRiskLayerCombobox.currentLayer()
            opacity = 0.8

        target_layer.loadNamedStyle(qml_filepath)
        target_layer.renderer().setOpacity(opacity)
        iface.layerTreeView().refreshLayerSymbology(target_layer.id())  # レイヤー一覧の凡例を更新
        target_layer.triggerRepaint()  # キャンバス上の見た目を更新

    def get_existing_filenames(self):
        """
        出力先フォルダに同名ファイルが存在するかチェック
        存在するファイルの配列を返す

        Returns:
            list
        """
        output_dir = self.main.zoningOutputDirFileWidget.filePath()
        existing_filenames = []

        for file_info in (OUTPUT_ZONING, OUTPUT_ZONING_THRESHOLDS_JSON):
            filename = f"{file_info['FILE_NAME']}.{file_info['EXTENSION']}"
            if os.path.exists(os.path.join(output_dir, filename)):
                existing_filenames.append(filename)

        return existing_filenames

    def run_zoning(self):
        # 既存のzoning.tifがある場合も実行を妨げない。
        # 出力側でWindowsロック/既存ファイルを検出し、zoning_v2.tif,
        # zoning_v3.tif ... のように安全に世代保存する。

        input_layers_dict = {
            "profit": self.main.zoningProfitLayerCombobox.currentLayer(),
            "risk": self.main.zoningRiskLayerCombobox.currentLayer(),
        }
        input_thresholds_dict = {
            "profit": self.main.zoningProfitSpinbox.value(),
            "risk": self.main.zoningRiskSpinbox.value(),
        }
        thread = processes.zoning.ProcessingThread(
            input_layers_dict,
            input_thresholds_dict,
            self.main.zoningOutputDirFileWidget.filePath(),
        )
        progress_dialog = ProgressDialog(thread.set_abort_flag)
        progress_dialog.set_abortable(False)
        thread.processStarted.connect(progress_dialog.set_sum_of_processes)
        thread.addProgress.connect(progress_dialog.add_progress)
        thread.postMessage.connect(progress_dialog.set_messsage)
        thread.setAbortable.connect(progress_dialog.set_abortable)
        thread.processFinished.connect(progress_dialog.close)
        thread.processFinished.connect(self.add_layers_to_project)
        thread.processFailed.connect(
            lambda error_message: QMessageBox.information(
                self.main, "エラー", f"エラーが発生しました。\n\n{error_message}"
            )
        )
        thread.start()
        progress_dialog.exec_()

        if thread.abort_flag:
            QMessageBox.information(self.main, "中断", "処理を中断しました。")
        else:
            QMessageBox.information(self.main, "終了", "処理が終了しました。")

    @staticmethod
    def add_layers_to_project(rlayers_dict):
        """ゾーニング結果をQGIS 3.44で安定してプロジェクトへ登録する。

        既存の壊れた/空の「ゾーニング図」グループを整理し、
        有効な結果レイヤだけを新しい結果グループへ追加する。
        """
        project = QgsProject.instance()
        root = project.layerTreeRoot()

        valid_layers = []
        for rlayer in rlayers_dict.values():
            if rlayer is None:
                continue
            try:
                if not rlayer.isValid():
                    continue
            except Exception:
                continue
            valid_layers.append(rlayer)

        if not valid_layers:
            return

        # 旧実行で残った同名結果レイヤをプロジェクトから除去。
        for layer in list(project.mapLayers().values()):
            try:
                if layer.name() == OUTPUT_ZONING["DISPLAY_NAME"] and layer not in valid_layers:
                    project.removeMapLayer(layer.id())
            except Exception:
                pass

        # 旧グループ参照を整理。「?」表示の原因となる空/壊れたノードを残さない。
        for child in list(root.children()):
            try:
                if isinstance(child, QgsLayerTreeGroup) and child.name() == OUTPUT_ZONING["DISPLAY_NAME"]:
                    root.removeChildNode(child)
            except Exception:
                pass

        group = root.insertGroup(0, OUTPUT_ZONING["DISPLAY_NAME"])
        group.setExpanded(True)

        for rlayer in valid_layers:
            if project.mapLayer(rlayer.id()) is None:
                project.addMapLayer(rlayer, False)
            group.addLayer(rlayer)
            try:
                rlayer.triggerRepaint()
            except Exception:
                pass

        try:
            iface.layerTreeView().refreshLayerSymbology(valid_layers[0].id())
            iface.mapCanvas().refresh()
        except Exception:
            pass

