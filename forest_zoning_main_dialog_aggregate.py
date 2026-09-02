# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

import os
import glob
from pathlib import Path

# QGIS-API
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import *

from . import processes
from .constants import OUTPUT_ZONING, OUTPUT_AGGREGATE, INPUT_DEM
from .utils import is_tmpdir_valid
from .progress_dialog import ProgressDialog



class ForestZoningMainDialogAggregate:
    """
    メイン画面の「集計」タブの処理を実装するクラス
    """
    def __init__(self, main):
        self.main = main
        self.init_aggregate_ui()

    def init_aggregate_ui(self):
        self.main.aggregateSetLayersButton.clicked.connect(
            self.set_aggregate_layer_combobox
        )
        self.main.aggregateSetDemButton.clicked.connect(self.load_aggregate_dem_path)
        self.main.aggregateZoningLayerCombobox.setFilters(
            QgsMapLayerProxyModel.RasterLayer
        )
        self.main.aggregatePolygonLayerCommbobox.setFilters(
            QgsMapLayerProxyModel.VectorLayer
        )
        self.main.aggregateRunButton.clicked.connect(self.run_aggregate)
        self.main.aggregateOutputDirFileWidget.setFilter("*.shp")
        filename = OUTPUT_AGGREGATE.get("FILE_NAME")
        self.main.aggregateOutputDirFileWidget.setDefaultRoot(f"{filename}.shp")

        self.main.aggregateZoningLayerCombobox.layerChanged.connect(
            self.refresh_aggregate_ui
        )
        self.main.aggregatePolygonLayerCommbobox.layerChanged.connect(
            self.refresh_aggregate_ui
        )
        self.main.aggregateOutputDirFileWidget.fileChanged.connect(
            self.refresh_aggregate_ui
        )
        self.main.aggregateDemFileWidget.fileChanged.connect(self.refresh_aggregate_ui)

        # ラジオボタンの変更時にUI更新
        # 一方のラジオボタンの変更が発火するともう一方も発火するので一方だけconnect
        self.main.radioButtonPolygon.toggled.connect(self.refresh_aggregate_ui)

        self.main.aggregateStyleThresholdspinBox.setValue(30)

        self.refresh_aggregate_ui()

    def set_aggregate_layer_combobox(self):
        """ゾーニング図・DEM・集計出力先を一括で自動設定する。

        zoning[_vN].tif の最大世代を優先し、そのファイル位置から
        ZoningKitルートを推定する。DEMは次の順で探索する。
        1. 要素計算タブで現在選択されているDEM
        2. <root>/DATA/DEM
        3. <root>/DEM
        出力先は <root>/ZONING/aggregate.shp とする。
        """
        project = QgsProject.instance()

        def source_path(layer):
            if layer is None:
                return ""
            try:
                value = layer.source()
                if value:
                    return value.split("|", 1)[0]
            except Exception:
                pass
            return ""

        def generation(path):
            import re
            stem = os.path.splitext(os.path.basename(path))[0].lower()
            wanted = OUTPUT_ZONING["FILE_NAME"].lower()
            if stem == wanted:
                return 0
            m = re.fullmatch(re.escape(wanted) + r"_v([0-9]+)", stem, re.I)
            return int(m.group(1)) if m else None

        # まずプロジェクト上の zoning[_vN] を実ファイル名で探索する。
        candidates = []
        for layer in project.mapLayers().values():
            if layer is None or layer.type() != QgsMapLayer.RasterLayer:
                continue
            path = source_path(layer)
            if not path:
                continue
            gen = generation(path)
            if gen is not None:
                candidates.append((gen, layer, path))

        # 表示名「ゾーニング図」もフォールバック候補。
        if not candidates:
            for layer in project.mapLayersByName(OUTPUT_ZONING["DISPLAY_NAME"]):
                path = source_path(layer)
                if path:
                    candidates.append((0, layer, path))

        if not candidates:
            QMessageBox.information(self.main, "エラー", "ゾーニング図を作成してください。")
            return

        candidates.sort(key=lambda x: x[0], reverse=True)
        _, zoning_layer, zoning_path = candidates[0]
        self.main.aggregateZoningLayerCombobox.setLayer(zoning_layer)

        zoning_dir = os.path.dirname(os.path.abspath(zoning_path))
        if os.path.basename(zoning_dir).lower() == "zoning":
            dataset_root = os.path.dirname(zoning_dir)
        else:
            dataset_root = zoning_dir

        # DEM候補: 要素計算で選択済みのDEMを最優先。
        dem_candidates = []
        try:
            current_dem = self.main.elementsDemFileWidget.filePath()
            if current_dem and os.path.isfile(current_dem):
                dem_candidates.append(current_dem)
        except Exception:
            pass

        def collect_tifs(folder):
            if not os.path.isdir(folder):
                return []
            found = []
            try:
                for name in os.listdir(folder):
                    lower = name.lower()
                    if lower.endswith(".tif") or lower.endswith(".tiff"):
                        path = os.path.join(folder, name)
                        if "_morizon_work" not in lower and ".aux." not in lower:
                            found.append(path)
            except OSError:
                return []
            return found

        for dem_dir in (
            os.path.join(dataset_root, "DATA", "DEM"),
            os.path.join(dataset_root, "DEM"),
        ):
            dem_candidates.extend(collect_tifs(dem_dir))

        # 重複除去。merge.tif / dem.tif を優先し、次にパスの短いもの。
        unique = []
        seen = set()
        for path in dem_candidates:
            norm = os.path.normcase(os.path.abspath(path))
            if norm not in seen:
                seen.add(norm)
                unique.append(path)

        def dem_rank(path):
            name = os.path.basename(path).lower()
            priority = 0 if name == "merge.tif" else (1 if name == "dem.tif" else 2)
            return (priority, len(Path(path).parts), len(path), path.lower())

        if unique:
            unique.sort(key=dem_rank)
            self.main.aggregateDemFileWidget.setFilePath(unique[0])

        # 集計出力先はZONING配下へ自動設定。
        try:
            os.makedirs(zoning_dir, exist_ok=True)
            output_path = os.path.join(
                zoning_dir, OUTPUT_AGGREGATE["FILE_NAME"] + ".shp"
            )
            self.main.aggregateOutputDirFileWidget.setFilePath(output_path)
            if hasattr(self.main.aggregateOutputDirFileWidget, "setDefaultRoot"):
                self.main.aggregateOutputDirFileWidget.setDefaultRoot(zoning_dir)
        except Exception:
            pass

        self.refresh_aggregate_ui()

    def load_aggregate_dem_path(self):
        """手動指定時もZoningKit/DATA/DEMのどこを選んでもDEMを探索する。"""
        selected_dir = QFileDialog.getExistingDirectory(
            self.main, "ZoningKit / DATA / DEM フォルダを選択"
        )
        if not selected_dir:
            return

        search_dirs = [
            selected_dir,
            os.path.join(selected_dir, "DEM"),
            os.path.join(selected_dir, "DATA", "DEM"),
        ]

        # 上位がDATA/DEMの場合も吸収
        parent = os.path.dirname(selected_dir)
        search_dirs.extend([
            os.path.join(parent, "DEM"),
            os.path.join(parent, "DATA", "DEM"),
        ])

        candidates = []
        for d in search_dirs:
            if not os.path.isdir(d):
                continue
            try:
                for name in os.listdir(d):
                    if name.lower().endswith((".tif", ".tiff")):
                        candidates.append(os.path.join(d, name))
            except OSError:
                pass

        if candidates:
            candidates.sort(
                key=lambda p: (
                    0 if os.path.basename(p).lower() == "merge.tif" else 1,
                    len(p),
                    p.lower(),
                )
            )
            self.main.aggregateDemFileWidget.setFilePath(candidates[0])
        else:
            self.main.aggregateDemFileWidget.setFilePath("")
            QMessageBox.information(
                self.main, "DEM未検出",
                "選択した場所からDEM（*.tif）を検出できませんでした。"
            )

    def run_aggregate(self):
        # GRASSエラーを回避するために環境変数に不正な文字がないか確認
        if not is_tmpdir_valid():
            QMessageBox.information(
                self.main,
                "エラー",
                f"TEMPディレクトリーに不正な文字があります。\nマニュアルに従い、システム環境変数を設定していください。",
            )
            return

        output_path = self.main.aggregateOutputDirFileWidget.filePath()
        zoning_rlayer = self.main.aggregateZoningLayerCombobox.currentLayer()

        def is_file_used(file_name):
            """ファイルが使用されているかをチェックする関数"""
            try:
                os.rename(file_name, file_name)
                return False
            except OSError:
                return True

        # .shpがすでに存在している場合、同名の.shp/.dbf/.shx/.prjファイルを削除する
        if os.path.exists(output_path):
            folderpath = os.path.dirname(output_path)
            filename_no_extension = os.path.splitext(os.path.basename(output_path))[0]
            # Shapefileの既知の構成ファイルだけを対象とし、同じbasenameを
            # 持つ利用者の無関係なファイルは削除しない。
            shapefile_extensions = {
                ".shp", ".shx", ".dbf", ".prj", ".qpj", ".cpg",
                ".sbn", ".sbx", ".fbn", ".fbx", ".ain", ".aih",
                ".ixs", ".mxs", ".atx", ".shp.xml", ".qml",
            }
            file_list = []
            for candidate in glob.glob(
                os.path.join(folderpath, f"{filename_no_extension}.*")
            ):
                candidate_name = os.path.basename(candidate).lower()
                matched_extension = candidate_name[len(filename_no_extension):]
                if matched_extension in shapefile_extensions:
                    file_list.append(candidate)

            # deletableを初期化
            deletable = True
            for file in file_list:
                if is_file_used(file) == True:
                    deletable = False
                    break

            if deletable == True:
                for file in file_list:
                    os.remove(file)
            else:
                # Windowsで参照中なら aggregate_v2.shp, _v3... へ安全に保存。
                base = os.path.splitext(output_path)[0]
                ext = os.path.splitext(output_path)[1] or ".shp"
                version = 2
                while True:
                    candidate = f"{base}_v{version}{ext}"
                    if not os.path.exists(candidate):
                        output_path = candidate
                        self.main.aggregateOutputDirFileWidget.setFilePath(output_path)
                        break
                    version += 1

        self.main.hide()

        mode = "polygon" if self.main.radioButtonPolygon.isChecked() else "dem"
        input_layer = self.main.aggregatePolygonLayerCommbobox.currentLayer() if mode=="polygon" else self.main.aggregateDemFileWidget.filePath()
        thread = processes.aggregate.ProcessingThread(
            mode=mode,
            zoning_layer_path=zoning_rlayer,
            input_layer=input_layer,
            output_path=output_path,
            style_threshold=self.main.aggregateStyleThresholdspinBox.value()
        )
        progress_dialog = ProgressDialog(thread.set_abort_flag)
        progress_dialog.set_abortable(False)
        thread.processStarted.connect(progress_dialog.set_sum_of_processes)
        thread.addProgress.connect(progress_dialog.add_progress)
        thread.postMessage.connect(progress_dialog.set_messsage)
        thread.processFinished.connect(self.add_layers_to_project)
        thread.processFinished.connect(progress_dialog.close)
        aggregate_state = {"failed": False}

        def on_failed(error_message):
            aggregate_state["failed"] = True
            progress_dialog.close()
            QMessageBox.information(
                self.main, "エラー", f"エラーが発生しました。\n\n{error_message}"
            )

        thread.processFailed.connect(on_failed)
        thread.start()
        progress_dialog.exec_()

        self.main.show()

        if not aggregate_state["failed"]:
            QMessageBox.information(self.main, "完了", "処理が完了しました。")

    def refresh_aggregate_ui(self):
        # ラジオボタンの状態に応じてUIを有効化・無効化
        self.main.aggregatePolygonLayerCommbobox.setEnabled(
            self.main.radioButtonPolygon.isChecked()
        )
        self.main.aggregateDemFileWidget.setEnabled(
            self.main.radioButtonWatershed.isChecked()
        )
        self.main.aggregateSetDemButton.setEnabled(
            self.main.radioButtonWatershed.isChecked()
        )

        error_texts = self.get_aggregate_error()
        has_no_error = len(error_texts) == 0
        self.main.aggregateErrorLabel.setText("\n".join(error_texts))
        self.main.aggregateRunButton.setEnabled(has_no_error)

    def get_aggregate_error(self) -> list:
        error_texts = []
        if self.main.aggregateZoningLayerCombobox.currentLayer() is None:
            error_texts.append("ゾーニング図を指定してください")
        if (
                self.main.radioButtonPolygon.isChecked()
                and self.main.aggregatePolygonLayerCommbobox.currentLayer() is None
        ):
            error_texts.append("ポリゴンレイヤを指定してください")
        if (
                self.main.radioButtonWatershed.isChecked()
                and self.main.aggregateDemFileWidget.filePath() == ""
        ):
            error_texts.append("DEMファイルを指定してください")
        if self.main.aggregateOutputDirFileWidget.filePath() == "":
            error_texts.append("出力先フォルダを指定してください")

        return error_texts

    @staticmethod
    def add_layers_to_project(rlayers_dict):
        """
        処理結果をプロジェクトに追加
        """
        for rlayer in rlayers_dict.values():
            # プロジェクトのレイヤー一覧の一番上にレイヤーを追加
            QgsProject.instance().addMapLayer(rlayer, False)
            root = QgsProject().instance().layerTreeRoot()
            root.insertLayer(0, rlayer)
