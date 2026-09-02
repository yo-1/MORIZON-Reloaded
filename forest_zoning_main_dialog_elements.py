# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

import os
import glob
import re

# QGIS-API
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import *


from .progress_dialog import ProgressDialog
from . import processes
from .constants import (
    INPUT_DEM,
    INPUT_NPP,
    INPUT_SRAD,
    INPUT_VTEX,
    INPUT_BUILDING,
    INPUT_NETWORK,
    INPUT_COSTCSV,
    OUTPUT_SITEIDX_HINOKI,
    OUTPUT_SITEIDX_KARAMATSU,
    OUTPUT_SITEIDX_SUGI,
    OUTPUT_COST,
    OUTPUT_DISTANCE,
    OUTPUT_SHC,
    OUTPUT_SLOPE,
    OUTPUT_SAVEAREA,
)
from .utils import is_tmpdir_valid
from pathlib import Path


class ForestZoningMainDialogElements:
    """
    メイン画面の「要素計算」タブの処理を実装するクラス
    """

    def __init__(self, main):
        self.main = main
        self.init_elements_ui()

    def init_elements_ui(self):
        # connect signals
        self.main.elementsRunPushButton.clicked.connect(self.run_elements)
        self.main.elementsLoadFromDirPushButton.clicked.connect(
            self.load_elements_files_from_dir
        )

        # QGIS 3.44 操作性改善:
        # ・前回選択フォルダを記憶
        # ・最近使ったデータセットを表示
        # ・ファイル選択ダイアログの開始位置を記憶
        self._dataset_settings = QSettings()
        self._settings_prefix = "MORIZON/elements"
        self._recent_dataset_limit = 8
        self._init_recent_dataset_ui()
        self._apply_last_directory_to_filewidgets()
        self._restore_last_output_dir()

        # QGIS 3.44 移植済み要素の有効化。
        # STEP5=地利、STEP6=地形の複雑さ、STEP7B=保全対象を含む流域。
        self._apply_migration_safety_mode()

        # 出力先変更を記憶
        self.main.elementsOutputDirFileWidget.fileChanged.connect(
            self._remember_output_dir
        )

        # UIの変更を検知しUI全体を更新する
        for signal in (
            self.main.elementsDemFileWidget.fileChanged,
            self.main.elementsNppFileWidget.fileChanged,
            self.main.elementsSradFileWidget.fileChanged,
            self.main.elementsVtexFileWidget.fileChanged,
            self.main.elementsBuildingFileWidget.fileChanged,
            self.main.elementsNetworkFileWidget.fileChanged,
            self.main.elementsCostCsvFileWidget.fileChanged,
            self.main.elementsSiteIdxCheckbox.stateChanged,
            self.main.elementsCostCheckbox.stateChanged,
            self.main.elementsDistanceCheckbox.stateChanged,
            self.main.elementsShcCheckbox.stateChanged,
            self.main.elementsSlopeCheckbox.stateChanged,
            self.main.elementsSaveareaCheckbox.stateChanged,
            self.main.elementsOutputDirFileWidget.fileChanged,
        ):
            signal.connect(self.refresh_elements_ui)

        self.refresh_elements_ui()

    def refresh_elements_ui(self):
        self.set_elements_filewidgets_enabled()
        self.main.elementsErrorLabel.setText("\n".join(self.get_elements_error_texts()))
        self.main.elementsRunPushButton.setEnabled(
            len(self.get_elements_error_texts()) == 0
        )

    def get_elements_mandatory_files_dict(self) -> dict:
        """
        チェックボックスの状態をもとに各データが必須か否かの辞書を取得する

        Returns:
            dict: {[key:str]: bool}
        """
        return {
            "dem": (
                self.main.elementsSiteIdxCheckbox.isChecked()
                or self.main.elementsCostCheckbox.isChecked()
                or self.main.elementsDistanceCheckbox.isChecked()
                or self.main.elementsShcCheckbox.isChecked()
                or self.main.elementsSlopeCheckbox.isChecked()
                or self.main.elementsSaveareaCheckbox.isChecked()
            ),
            "npp": self.main.elementsSiteIdxCheckbox.isChecked(),
            "srad": self.main.elementsSiteIdxCheckbox.isChecked(),
            "vtex": self.main.elementsSiteIdxCheckbox.isChecked(),
            "building": self.main.elementsSaveareaCheckbox.isChecked(),
            "network": self.main.elementsDistanceCheckbox.isChecked(),
            "costcsv": self.main.elementsCostCheckbox.isChecked(),
        }

    def set_elements_filewidgets_enabled(self):
        mondatory_files_dict = self.get_elements_mandatory_files_dict()
        self.main.elementsDemFileWidget.setEnabled(mondatory_files_dict["dem"])
        self.main.elementsNppFileWidget.setEnabled(mondatory_files_dict["npp"])
        self.main.elementsSradFileWidget.setEnabled(mondatory_files_dict["srad"])
        self.main.elementsVtexFileWidget.setEnabled(mondatory_files_dict["vtex"])
        self.main.elementsBuildingFileWidget.setEnabled(
            mondatory_files_dict["building"]
        )
        self.main.elementsNetworkFileWidget.setEnabled(mondatory_files_dict["network"])
        self.main.elementsCostCsvFileWidget.setEnabled(mondatory_files_dict["costcsv"])

    def get_elements_error_texts(self) -> list:
        """
        要素計算タブのUIの状態が不正な場合、全ての不正項目についてエラー文の配列を返す

        Returns:
            [list[str]]
        """
        error_texts = []

        def validate_input(filepath: str, input_name: str):
            """
            入力データのバリデーション
            """
            if filepath == "":
                error_texts.append(f"{input_name}を設定してください")
            else:
                if re.search("[^\x01-\x7E]", filepath):
                    error_texts.append(f"{input_name}のファイルパスに全角文字列が含まれています")

        # 必須データをバリデーション
        mondatory_files_dict = self.get_elements_mandatory_files_dict()
        if mondatory_files_dict["dem"]:
            validate_input(
                self.main.elementsDemFileWidget.filePath(), INPUT_DEM["DISPLAY_NAME"]
            )
        if mondatory_files_dict["npp"]:
            validate_input(
                self.main.elementsNppFileWidget.filePath(), INPUT_NPP["DISPLAY_NAME"]
            )
        if mondatory_files_dict["srad"]:
            validate_input(
                self.main.elementsSradFileWidget.filePath(), INPUT_SRAD["DISPLAY_NAME"]
            )
        if mondatory_files_dict["vtex"]:
            validate_input(
                self.main.elementsVtexFileWidget.filePath(), INPUT_VTEX["DISPLAY_NAME"]
            )
        if mondatory_files_dict["building"]:
            validate_input(
                self.main.elementsBuildingFileWidget.filePath(),
                INPUT_BUILDING["DISPLAY_NAME"],
            )
        if mondatory_files_dict["network"]:
            validate_input(
                self.main.elementsNetworkFileWidget.filePath(),
                INPUT_NETWORK["DISPLAY_NAME"],
            )
        if mondatory_files_dict["costcsv"]:
            validate_input(
                self.main.elementsCostCsvFileWidget.filePath(),
                INPUT_COSTCSV["DISPLAY_NAME"],
            )

        def validate_output(output_name: str):
            """
            出力データのバリデーション
            """
            groups = QgsProject().instance().layerTreeRoot().findGroups()
            group_names = list(map(lambda g: g.name(), groups))
            if output_name in group_names:
                error_texts.append(f"プロジェクトにすでに「{output_name}」が存在します")

        if self.main.elementsSiteIdxCheckbox.isChecked():
            validate_output(OUTPUT_SITEIDX_SUGI["DISPLAY_NAME"])
            validate_output(OUTPUT_SITEIDX_HINOKI["DISPLAY_NAME"])
            validate_output(OUTPUT_SITEIDX_KARAMATSU["DISPLAY_NAME"])
        if self.main.elementsCostCheckbox.isChecked():
            validate_output(OUTPUT_COST["DISPLAY_NAME"])
        if self.main.elementsDistanceCheckbox.isChecked():
            validate_output(OUTPUT_DISTANCE["DISPLAY_NAME"])
        if self.main.elementsShcCheckbox.isChecked():
            validate_output(OUTPUT_SHC["DISPLAY_NAME"])
        if self.main.elementsSlopeCheckbox.isChecked():
            validate_output(OUTPUT_SLOPE["DISPLAY_NAME"])
        if self.main.elementsSaveareaCheckbox.isChecked():
            validate_output(OUTPUT_SAVEAREA["DISPLAY_NAME"])

        # その他
        if not mondatory_files_dict["dem"]:
            error_texts.append("計算する要素をひとつ以上選択してください")
        if self.main.elementsOutputDirFileWidget.filePath() == "":
            error_texts.append("出力先フォルダを指定してください")

        return error_texts

    def _init_recent_dataset_ui(self):
        """
        「最近使ったデータセット」コンボを実行時に追加する。
        .uiファイルを大きく変更せず、旧MORIZONの画面構成を維持する。
        """
        self.main.elementsRecentDatasetComboBox = QComboBox(self.main)
        self.main.elementsRecentDatasetComboBox.setMinimumWidth(260)
        self.main.elementsRecentDatasetComboBox.setToolTip(
            "最近使用したZoningKitを選択すると、入力データを自動設定します。"
        )
        self.main.elementsRecentDatasetComboBox.currentIndexChanged.connect(
            self._on_recent_dataset_selected
        )

        # 「フォルダから一括読み込み」ボタンと同じ行へ追加
        self.main.horizontalLayout.addWidget(QLabel("最近使ったデータセット:"))
        self.main.horizontalLayout.addWidget(
            self.main.elementsRecentDatasetComboBox, 1
        )
        self._reload_recent_dataset_combo()

    def _settings_value(self, key, default=""):
        value = self._dataset_settings.value(
            f"{self._settings_prefix}/{key}", default
        )
        return "" if value is None else str(value)

    def _recent_datasets(self):
        value = self._dataset_settings.value(
            f"{self._settings_prefix}/recentDatasets", []
        )
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        result = []
        for p in value:
            p = os.path.normpath(str(p))
            if p and p not in result:
                result.append(p)
        return result[:self._recent_dataset_limit]

    def _save_recent_dataset(self, dataset_root):
        dataset_root = os.path.normpath(dataset_root)
        recent = [p for p in self._recent_datasets() if p != dataset_root]
        recent.insert(0, dataset_root)
        recent = recent[:self._recent_dataset_limit]

        self._dataset_settings.setValue(
            f"{self._settings_prefix}/recentDatasets", recent
        )
        self._dataset_settings.setValue(
            f"{self._settings_prefix}/lastDataset", dataset_root
        )
        self._dataset_settings.setValue(
            f"{self._settings_prefix}/lastBrowseDir", dataset_root
        )
        self._dataset_settings.sync()
        self._reload_recent_dataset_combo()

    def _reload_recent_dataset_combo(self):
        combo = getattr(self.main, "elementsRecentDatasetComboBox", None)
        if combo is None:
            return

        combo.blockSignals(True)
        combo.clear()
        combo.addItem("選択してください", "")
        for dataset_root in self._recent_datasets():
            name = os.path.basename(dataset_root.rstrip("\\/")) or dataset_root
            combo.addItem(f"{name}  —  {dataset_root}", dataset_root)
        combo.setCurrentIndex(0)
        combo.blockSignals(False)

    def _on_recent_dataset_selected(self, index):
        combo = self.main.elementsRecentDatasetComboBox
        dataset_root = combo.itemData(index)
        if not dataset_root:
            return
        if not os.path.isdir(dataset_root):
            QMessageBox.warning(
                self.main,
                "MORIZON",
                "保存されているデータセットフォルダが見つかりません。\n"
                + dataset_root,
            )
            return
        self._load_dataset(dataset_root, remember=True)

    def _apply_last_directory_to_filewidgets(self):
        """
        各「...」ボタンで開くQgsFileWidgetの開始位置を前回位置へ合わせる。
        QGISのバージョン差に備え、setDefaultRootがある場合のみ利用する。
        """
        last_dir = self._settings_value("lastBrowseDir", "")
        if not last_dir or not os.path.isdir(last_dir):
            return

        for widget in (
            self.main.elementsDemFileWidget,
            self.main.elementsNppFileWidget,
            self.main.elementsSradFileWidget,
            self.main.elementsVtexFileWidget,
            self.main.elementsBuildingFileWidget,
            self.main.elementsNetworkFileWidget,
            self.main.elementsCostCsvFileWidget,
        ):
            if hasattr(widget, "setDefaultRoot"):
                widget.setDefaultRoot(last_dir)

        last_output = self._settings_value("lastOutputDir", "")
        output_root = last_output if os.path.isdir(last_output) else last_dir
        if hasattr(self.main.elementsOutputDirFileWidget, "setDefaultRoot"):
            self.main.elementsOutputDirFileWidget.setDefaultRoot(output_root)

    def _remember_output_dir(self, path):
        path = "" if path is None else str(path).strip()
        if not path:
            return
        # QgsFileWidgetではファイル風に返る場合もあるため、ディレクトリだけ保存
        norm = os.path.normpath(path)
        self._dataset_settings.setValue(
            f"{self._settings_prefix}/lastOutputDir", norm
        )
        self._dataset_settings.sync()

    def _restore_last_output_dir(self):
        current = self.main.elementsOutputDirFileWidget.filePath()
        if current:
            return
        last_output = self._settings_value("lastOutputDir", "")
        if last_output and os.path.isdir(last_output):
            self.main.elementsOutputDirFileWidget.setFilePath(last_output)
            if hasattr(self.main.elementsOutputDirFileWidget, "setDefaultRoot"):
                self.main.elementsOutputDirFileWidget.setDefaultRoot(last_output)

    def _apply_migration_safety_mode(self):
        """QGIS 3.44へ移植済みのSTEP5～STEP7Bを有効化する。"""
        self.main.elementsDistanceCheckbox.setEnabled(True)
        self.main.elementsDistanceCheckbox.setToolTip(
            "STEP5 QGIS 3.44安定版: 10m解析DEMと同一グリッドで既設路網までの距離を計算します。"
        )
        self.main.elementsShcCheckbox.setEnabled(True)
        self.main.elementsShcCheckbox.setToolTip(
            "STEP6 QGIS 3.44安定版: 林野庁MORIZON仕様のSHC（平面曲率の標準偏差）を計算します。"
        )
        self.main.elementsSaveareaCheckbox.setEnabled(True)
        self.main.elementsSaveareaCheckbox.setToolTip(
            "STEP7B 林野庁原版照合済み: r.watershed threshold=500の流域区分と建物重複から保全対象を含む流域を判定します。"
        )

    def _find_dataset_root_and_data_dir(self, selected_dir):
        """
        ZoningKitルート、DATAフォルダ、その配下のどこを選んでも
        ZoningKitルートとDATAフォルダを推定する。

        例:
          .../ZoningKit_09
          .../ZoningKit_09/DATA
          .../ZoningKit_09/DATA/DEM
          .../ZoningKit_09/DATA/SiteIndex/NPP
        のいずれでもよい。
        """
        selected_dir = os.path.abspath(selected_dir)

        # 選択場所から上方向へDATAを探す
        cur = selected_dir
        for _ in range(8):
            if os.path.basename(cur).lower() == "data":
                return os.path.dirname(cur), cur
            candidate = os.path.join(cur, "DATA")
            if os.path.isdir(candidate):
                return cur, candidate
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent

        # 選択場所の下方向を最大3階層だけ探索
        base_depth = selected_dir.rstrip(os.sep).count(os.sep)
        try:
            for root, dirs, _files in os.walk(selected_dir):
                depth = root.rstrip(os.sep).count(os.sep) - base_depth
                if depth > 3:
                    dirs[:] = []
                    continue
                for d in dirs:
                    if d.lower() == "data":
                        data_dir = os.path.join(root, d)
                        return root, data_dir
        except OSError:
            pass

        # 旧仕様互換: 選択フォルダそのものをDATA相当として扱う
        return os.path.dirname(selected_dir), selected_dir

    def _case_insensitive_candidates(self, folder, extension):
        if not os.path.isdir(folder):
            return []
        ext = "." + extension.lower().lstrip(".")
        candidates = []
        try:
            for root, _dirs, files in os.walk(folder):
                for name in files:
                    lname = name.lower()
                    if lname.endswith(ext) or (ext == ".tif" and ".tif" in lname):
                        candidates.append(os.path.join(root, name))
        except OSError:
            return []
        return candidates

    def _pick_best_file(self, data_dir, input_def):
        """
        既定サブフォルダを優先しつつ、多少フォルダ構成が異なっても
        対象拡張子を探索する。
        """
        expected_dir = os.path.join(data_dir, *input_def["PATH"])
        candidates = self._case_insensitive_candidates(
            expected_dir, input_def["EXT"]
        )

        # 既定場所に無い場合のみDATA配下全体から探索
        if not candidates:
            all_candidates = self._case_insensitive_candidates(
                data_dir, input_def["EXT"]
            )
            keywords = [p.lower() for p in input_def["PATH"]]
            filtered = []
            for f in all_candidates:
                lower = f.lower()
                if all(k in lower for k in keywords):
                    filtered.append(f)
            candidates = filtered

        if not candidates:
            return ""

        # 一時成果・auxファイルを避け、短いパスを優先
        candidates = [
            f for f in candidates
            if "_morizon_work" not in f.lower()
            and ".aux." not in f.lower()
        ] or candidates
        candidates.sort(key=lambda p: (len(Path(p).parts), len(p), p.lower()))
        return candidates[0]

    def _load_dataset(self, selected_dir, remember=True):
        dataset_root, data_dir = self._find_dataset_root_and_data_dir(selected_dir)

        found = 0
        for input_def, filewidget in (
            (INPUT_DEM, self.main.elementsDemFileWidget),
            (INPUT_NPP, self.main.elementsNppFileWidget),
            (INPUT_SRAD, self.main.elementsSradFileWidget),
            (INPUT_VTEX, self.main.elementsVtexFileWidget),
            (INPUT_BUILDING, self.main.elementsBuildingFileWidget),
            (INPUT_NETWORK, self.main.elementsNetworkFileWidget),
            (INPUT_COSTCSV, self.main.elementsCostCsvFileWidget),
        ):
            filepath = self._pick_best_file(data_dir, input_def)
            if filepath:
                filewidget.setFilePath(filepath)
                found += 1

        # ZoningKitの標準YOUSOフォルダを自動設定。
        # 存在しない場合も自動作成するため、深い階層まで毎回選択する必要はない。
        output_dir = os.path.join(dataset_root, "YOUSO")
        try:
            os.makedirs(output_dir, exist_ok=True)
            self.main.elementsOutputDirFileWidget.setFilePath(output_dir)
            self._remember_output_dir(output_dir)
        except OSError:
            # 読み取り専用などで作れない場合は、前回出力先を維持
            self._restore_last_output_dir()

        if remember:
            self._save_recent_dataset(dataset_root)

        # 各ファイル選択の開始位置も今回のデータセットへ更新
        self._dataset_settings.setValue(
            f"{self._settings_prefix}/lastBrowseDir", dataset_root
        )
        self._dataset_settings.sync()
        self._apply_last_directory_to_filewidgets()

        self.refresh_elements_ui()

        if found == 0:
            QMessageBox.warning(
                self.main,
                "MORIZON",
                "入力データを自動検出できませんでした。\n"
                "ZoningKitフォルダ、DATAフォルダ、またはその配下を選択してください。",
            )
        return found

    def load_elements_files_from_dir(self):
        """
        前回位置を開始フォルダとして表示し、
        ZoningKit/DATA/その配下のどこを選んでも入力ファイルを自動探索する。
        """
        last_dir = self._settings_value("lastBrowseDir", "")
        if not os.path.isdir(last_dir):
            last_dir = QDir.homePath()

        selected_dir = QFileDialog.getExistingDirectory(
            self.main,
            "ZoningKit / DATA フォルダを選択",
            last_dir,
            QFileDialog.ShowDirsOnly,
        )

        # キャンセル時は何もしない
        if not selected_dir:
            return

        self._load_dataset(selected_dir, remember=True)

    def elements_get_existing_filenames(self) -> list:
        """
        「要素計算」で、出力先フォルダに同名ファイルが存在するかチェック
        存在する場合そのすべてのファイル名の配列を返す

        Returns:
            list
        """
        output_dir = self.main.elementsOutputDirFileWidget.filePath()
        existing_filenames = []

        def append_filename_if_exist(filename: str):
            if os.path.exists(os.path.join(output_dir, filename + ".tif")):
                existing_filenames.append(filename + ".tif")

        if self.main.elementsSiteIdxCheckbox.isChecked():
            append_filename_if_exist(OUTPUT_SITEIDX_SUGI["FILE_NAME"])
            append_filename_if_exist(OUTPUT_SITEIDX_HINOKI["FILE_NAME"])
            append_filename_if_exist(OUTPUT_SITEIDX_KARAMATSU["FILE_NAME"])
        if self.main.elementsCostCheckbox.isChecked():
            append_filename_if_exist(OUTPUT_COST["FILE_NAME"])
        if self.main.elementsDistanceCheckbox.isChecked():
            append_filename_if_exist(OUTPUT_DISTANCE["FILE_NAME"])
        if self.main.elementsShcCheckbox.isChecked():
            append_filename_if_exist(OUTPUT_SHC["FILE_NAME"])
        if self.main.elementsSlopeCheckbox.isChecked():
            append_filename_if_exist(OUTPUT_SLOPE["FILE_NAME"])
        if self.main.elementsSaveareaCheckbox.isChecked():
            append_filename_if_exist(OUTPUT_SAVEAREA["FILE_NAME"])

        return existing_filenames

    def _release_existing_output_layers(self, existing_filenames: list):
        """
        STEP7B4:
        上書き対象GeoTIFFを保持しているQGIS側参照をできるだけ全て切ってから
        Windowsのファイルロック解除を待つ。

        重要:
        旧版 get_raster_stats() の lru_cache は QgsRasterLayer 自体をキーとして
        強参照を保持するため、レイヤツリーから削除してもGeoTIFFがロックされたまま
        になることがあった。STEP7B4ではキャッシュ自体を廃止し、旧キャッシュが
        メモリ上に残っている場合も明示的にclearする。
        """
        if not existing_filenames:
            return

        output_dir = os.path.normcase(os.path.abspath(
            self.main.elementsOutputDirFileWidget.filePath()
        ))
        target_paths = {
            os.path.normcase(os.path.abspath(os.path.join(output_dir, name)))
            for name in existing_filenames
        }

        def _norm_layer_source(layer):
            try:
                src = layer.source().split("|", 1)[0]
                return os.path.normcase(os.path.abspath(src))
            except Exception:
                return ""

        project = QgsProject.instance()

        # 1. スコアリングタブの QgsMapLayerComboBox が対象レイヤを保持していれば先に解除。
        #    コンボボックスはプロジェクト削除後も currentLayer() を保持する場合がある。
        combo_names = (
            "scoringSiteidxLayerCombobox",
            "scoringCostLayerCombobox",
            "scoringDistanceLayerCombobox",
            "scoringShcLayerCombobox",
            "scoringSlopeLayerCombobox",
            "scoringSaveareaLayerCombobox",
        )
        for name in combo_names:
            combo = getattr(self.main, name, None)
            if combo is None:
                continue
            try:
                lyr = combo.currentLayer()
                if lyr is not None and _norm_layer_source(lyr) in target_paths:
                    if hasattr(combo, "setLayer"):
                        combo.setLayer(None)
                    elif hasattr(combo, "setCurrentIndex"):
                        combo.setCurrentIndex(-1)
            except Exception:
                pass

        # 2. 旧版の統計キャッシュがメモリに残っていればclear。
        try:
            from . import utils as morizon_utils
            cache_clear = getattr(morizon_utils.get_raster_stats, "cache_clear", None)
            if callable(cache_clear):
                cache_clear()
        except Exception:
            pass

        # 3. プロジェクト内で同じGeoTIFFを参照する全レイヤを削除。
        remove_ids = []
        for layer in list(project.mapLayers().values()):
            if _norm_layer_source(layer) in target_paths:
                remove_ids.append(layer.id())

        if remove_ids:
            project.removeMapLayers(remove_ids)

        # 4. 空グループを除去。
        root = project.layerTreeRoot()
        for group in list(root.findGroups()):
            try:
                if len(group.children()) == 0:
                    root.removeChildNode(group)
            except Exception:
                pass

        # 5. QtのdeleteLaterとPython参照を解放。
        import gc
        import time

        QCoreApplication.processEvents()
        try:
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        except Exception:
            pass
        QCoreApplication.processEvents()
        gc.collect()

        # 6. Windowsロック解放待ち＋削除。
        locked = []
        for path in sorted(target_paths):
            if not os.path.exists(path):
                continue

            released = False
            last_error = None

            # 最大約5秒待つ。通常は数百ms以内に解放される。
            for _ in range(25):
                try:
                    os.remove(path)
                    released = True
                    break
                except PermissionError as e:
                    last_error = e
                    QCoreApplication.processEvents()
                    try:
                        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
                    except Exception:
                        pass
                    gc.collect()
                    time.sleep(0.20)
                except OSError as e:
                    last_error = e
                    break

            if not released and os.path.exists(path):
                locked.append((path, last_error))

        # STEP7B5:
        # Windows上でなおロックが残っていても、ここでは処理を中断しない。
        # 各writer側で「新規世代ファイルへ出力」できるものは継続する。
        # 特にY_13_hozen.tifは savearea.generate() が _v2, _v3... へ安全に退避する。
        #
        # 戻り値は診断用。現時点では呼び出し側でエラー扱いにしない。
        return locked


    def _resolve_building_crs_override(self, building_path):
        """保全対象データのCRSを、QGISレイヤとして開く前に確認する。

        QGIS 3.44ではCRSなしShapeをQgsVectorLayerとして生成した時点で
        QGIS標準のCRS選択ダイアログが先に表示されることがある。
        そのためpreflightではOGRだけを使ってCRS/範囲を確認し、
        CRS不明時はMORIZON独自ダイアログを先に表示する。
        """
        if not building_path:
            return True, None

        source_path = str(building_path).split('|', 1)[0]

        # IMPORTANT:
        # ここでは QgsVectorLayer を生成しない。
        # CRSなしデータでQGIS標準CRSダイアログが先に出るのを防ぐ。
        try:
            from osgeo import ogr
            ds = ogr.Open(source_path, 0)
            if ds is None:
                QMessageBox.warning(
                    self.main, "保全対象データ",
                    "保全対象データを開けません。\n" + source_path
                )
                return False, None
            ogr_layer = ds.GetLayer(0)
            if ogr_layer is None:
                ds = None
                QMessageBox.warning(
                    self.main, "保全対象データ",
                    "保全対象データのレイヤを取得できません。\n" + source_path
                )
                return False, None

            srs = ogr_layer.GetSpatialRef()
            extent = ogr_layer.GetExtent()  # minX, maxX, minY, maxY

            # OGRで元データにCRSが明示されているなら、MORIZON側の確認は不要。
            if srs is not None:
                try:
                    wkt = srs.ExportToWkt()
                except Exception:
                    wkt = ""
                if wkt:
                    ds = None
                    return True, None

            if extent:
                extent_text = (
                    f"X: {extent[0]:.6f} ～ {extent[1]:.6f}\n"
                    f"Y: {extent[2]:.6f} ～ {extent[3]:.6f}"
                )
            else:
                extent_text = "取得できません"
            ds = None

        except Exception as e:
            QMessageBox.warning(
                self.main, "保全対象データ",
                "保全対象データのCRS確認に失敗しました。\n" + str(e)
            )
            return False, None

        # CRS不明の場合、まずMORIZON独自ダイアログを表示する。
        box = QMessageBox(self.main)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle("保全対象データの座標参照系")
        box.setText(
            "保全対象データに座標参照系（CRS）が設定されていません。\n\n"
            "基盤地図情報の建物データの場合は、JGD2011の地理座標系 "
            "（EPSG:6668）として処理できます。\n"
            "DM、自治体GIS、その他のデータの場合は、元データのCRSを指定してください。"
        )
        box.setInformativeText(
            "データの座標範囲:\n" + extent_text +
            "\n\n※元のShapeファイルは変更しません。MORIZONの今回の処理内だけでCRSを設定します。"
        )
        btn_fgd = box.addButton("基盤地図情報（EPSG:6668）", QMessageBox.AcceptRole)
        btn_select = box.addButton("CRSを指定...", QMessageBox.ActionRole)
        btn_cancel = box.addButton(QMessageBox.Cancel)
        box.setDefaultButton(btn_fgd)
        box.exec_()

        clicked = box.clickedButton()
        if clicked == btn_cancel or clicked is None:
            return False, None

        if clicked == btn_fgd:
            crs = QgsCoordinateReferenceSystem("EPSG:6668")
            if not crs.isValid():
                QMessageBox.critical(self.main, "CRSエラー", "EPSG:6668を読み込めませんでした。")
                return False, None
            return True, crs.authid() or crs.toWkt()

        # QGIS標準のCRS選択画面は、このボタンを押した場合だけ表示する。
        if clicked == btn_select:
            dlg = QgsProjectionSelectionDialog(self.main)
            dlg.setWindowTitle("保全対象データの座標参照系を指定")
            try:
                dlg.setCrs(QgsCoordinateReferenceSystem("EPSG:6668"))
            except Exception:
                pass
            if dlg.exec_() != QDialog.Accepted:
                return False, None
            crs = dlg.crs()
            if not crs.isValid():
                QMessageBox.warning(self.main, "CRSエラー", "有効な座標参照系を選択してください。")
                return False, None
            return True, crs.authid() or crs.toWkt()

        return False, None

    def run_elements(self):
        # STEP7F: CRS確認ダイアログを確実に前面表示するため、
        # 入力検証・CRS preflight が終わるまではメイン画面を非表示にしない。

        existing_filenames = self.elements_get_existing_filenames()
        if len(existing_filenames) > 0:
            if QMessageBox.No == QMessageBox.question(
                self.main,
                "上書き確認",
                "出力先フォルダに同名ファイルが存在します、上書きしますか？\n" + "\n".join(existing_filenames),
                QMessageBox.Yes,
                QMessageBox.No,
            ):
                QMessageBox.information(self.main, "処理中断", "処理を中断しました。")
                self.main.show()
                return

            # STEP5A: 上書き対象を参照しているQGISレイヤを自動解除し、
            # WindowsのGeoTIFFファイルロックを処理開始前に解放する。
            try:
                locked_outputs = self._release_existing_output_layers(existing_filenames)
                if locked_outputs:
                    # ロックが残る場合も処理継続。
                    # 対応writerは世代付きファイルへ出力し、新しい結果をQGISへ登録する。
                    QgsMessageLog.logMessage(
                        "既存MORIZON出力の一部にWindowsロックが残っています。"
                        "処理は安全な新規出力へ継続します: "
                        + ", ".join(path for path, _err in locked_outputs),
                        "MORIZON",
                        Qgis.Warning
                    )
            except Exception as e:
                QMessageBox.information(
                    self.main,
                    "既存出力の解放処理でエラー",
                    str(e)
                )
                self.main.show()
                return

        input_files_dict = {
            "dem": self.main.elementsDemFileWidget.filePath(),
            "npp": self.main.elementsNppFileWidget.filePath(),
            "srad": self.main.elementsSradFileWidget.filePath(),
            "vtex": self.main.elementsVtexFileWidget.filePath(),
            "building": self.main.elementsBuildingFileWidget.filePath(),
            "network": self.main.elementsNetworkFileWidget.filePath(),
            "costcsv": self.main.elementsCostCsvFileWidget.filePath(),
        }

        target_elements_dict = {
            "siteidx": self.main.elementsSiteIdxCheckbox.isChecked(),
            "cost": self.main.elementsCostCheckbox.isChecked(),
            "distance": self.main.elementsDistanceCheckbox.isChecked(),
            "shc": self.main.elementsShcCheckbox.isChecked(),
            "slope": self.main.elementsSlopeCheckbox.isChecked(),
            "savearea": self.main.elementsSaveareaCheckbox.isChecked(),
        }

        # STEP7 CRS preflight:
        # ProcessingThread内ではGUIダイアログを安全に表示できないため、
        # 保全対象のCRS不明時だけ処理開始前にユーザーへ確認する。
        input_files_dict["building_crs_override_authid"] = None
        if target_elements_dict["savearea"]:
            ok, override_authid = self._resolve_building_crs_override(
                input_files_dict["building"]
            )
            if not ok:
                QMessageBox.information(self.main, "処理中断", "保全対象データのCRS確認をキャンセルしました。")
                self.main.show()
                return
            input_files_dict["building_crs_override_authid"] = override_authid

        # ここまでで入力確認とCRS選択が完了。以降は進捗ダイアログ表示のため
        # 従来どおりメイン画面を隠す。
        self.main.hide()

        # SAGA・GRASSエラーを回避するために環境変数に不正な文字がないか確認
        if (
            target_elements_dict["distance"]
            or target_elements_dict["shc"]
            or target_elements_dict["savearea"]
        ):
            if not is_tmpdir_valid():
                QMessageBox.information(
                    self.main,
                    "エラー",
                    f"TEMPディレクトリーに不正な文字があります。\nマニュアルに従い、システム環境変数を設定していください。",
                )
                self.main.show()
                return

        # UIをブロックしないように別スレッドで処理を動かす
        thread = processes.elements.ProcessingThread(
            input_files_dict,
            target_elements_dict,
            self.main.elementsOutputDirFileWidget.filePath(),
        )
        progress_dialog = ProgressDialog(thread.set_abort_flag)
        thread.processStarted.connect(progress_dialog.set_sum_of_processes)
        thread.addProgress.connect(progress_dialog.add_progress)
        thread.postMessage.connect(progress_dialog.set_messsage)
        thread.setAbortable.connect(progress_dialog.set_abortable)
        thread.processFinished.connect(progress_dialog.close)
        thread.processFinished.connect(self.add_elements_layer_to_project)
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

        self.main.show()

    @staticmethod
    def add_elements_layer_to_project(output_rlayers_dict):
        """
        要素計算の処理結果を受け取って各要素ごとの2レイヤーを1つのグループとしてプロジェクトに追加
        """
        for display_name, rlayers in reversed(list(output_rlayers_dict.items())):
            root = QgsProject().instance().layerTreeRoot()
            group_node = root.insertGroup(0, display_name)
            group_node.setExpanded(False)

            for rlayer in rlayers:
                # QMLでの定義がQGISの不具合で反映されないのでコードでも設定する
                rlayer.setBlendMode(QPainter.CompositionMode_Multiply)

                QgsProject.instance().addMapLayer(rlayer, False)
                group_node.addLayer(rlayer)
