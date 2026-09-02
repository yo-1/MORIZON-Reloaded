# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

import os
import json
import re

# QGIS-API
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import *
from qgis.utils import iface

from .settings_manager import SettingsManager
from .progress_dialog import ProgressDialog

from .forest_zoning_scoring_stats_dialog import ForestZoningScoringStatsDialog
from .processes.raster_styler import (
    write_qml_by_thresholds_and_colors,
)
from . import processes
from .processes import raster_styler
from . import utils
from .constants import (
    OUTPUT_SITEIDX_HINOKI,
    OUTPUT_SITEIDX_KARAMATSU,
    OUTPUT_SITEIDX_SUGI,
    OUTPUT_COST,
    OUTPUT_DISTANCE,
    OUTPUT_SHC,
    OUTPUT_SLOPE,
    OUTPUT_SAVEAREA,
    OUTPUT_PARAMS_JSON,
    OUTPUT_PROFIT,
    OUTPUT_RISK,
    SCORING_COLORS_SITEIDX,
    SCORING_COLORS_DISTANCE,
    SCORING_COLORS_COST,
    SCORING_COLORS_SLOPE,
    SCORING_COLORS_SHC,
)


class ScoringObject:
    """
    スコアリングUIの各パラメタのcombobox、threshold1_spinbox、threshold2_spinboxを統合するクラス
    """

    def __init__(
        self,
        combobox: QgsMapLayerComboBox,
        threshold1_spinbox: QDoubleSpinBox,
        threshold2_spinbox: QDoubleSpinBox,
        laye_name: str,
    ):
        self.combobox = combobox
        self.threshold1_spinbox = threshold1_spinbox
        self.threshold2_spinbox = threshold2_spinbox
        self.layer_name = laye_name
        self.threshold_history_list = []

    def append_threshold_history(self, threshold: list):
        self.threshold_history_list.append(threshold)

    def reset_threshold_history(self, init_threshold: list):
        self.threshold_history_list = [init_threshold]

    def get_scoring_colors(self):
        if self.layer_name == "siteidx":
            scoring_colors = SCORING_COLORS_SITEIDX
        if self.layer_name == "distance":
            scoring_colors = SCORING_COLORS_DISTANCE
        if self.layer_name == "cost":
            scoring_colors = SCORING_COLORS_COST
        if self.layer_name == "slope":
            scoring_colors = SCORING_COLORS_SLOPE
        if self.layer_name == "shc":
            scoring_colors = SCORING_COLORS_SHC
        return scoring_colors

    def get_scores(self):
        settings_manager = SettingsManager()
        scores = settings_manager.get_setting(f"scores_{self.layer_name}")

        return scores


def get_initial_thresholds_of(obj: ScoringObject):
    if obj.layer_name == "slope":  # 「傾斜」だけはしきい値が固定値
        thresholds = (35, 45)
    elif obj.combobox.currentLayer() is not None and utils.is_valid_elements_layer(
        obj.combobox.currentLayer()
    ):
        thresholds = utils.get_initial_thresholds(obj.combobox.currentLayer())
    else:
        thresholds = (0, 0)

    return thresholds


class ForestZoningMainDialogScoring:
    """
    メイン画面の「スコアリング」タブの処理を実装するクラス
    """

    def __init__(self, main):
        self.main = main
        self.init_scoring_ui()

    def init_scoring_ui(self):
        # params.json を明示的に読み込んだ後は、レイヤー自動設定によって
        # 比較条件（しきい値）をQuantile初期値へ戻さない。
        self._scoring_params_loaded = False

        self.main.scoringRunPushButton.clicked.connect(self.run_scoring)
        self.set_scoring_score_labels_from_settings()
        self.main.scoringSetLayersPushbutton.clicked.connect(
            self.set_scoring_layer_combobox
        )

        self.scoring_objs_dict = {
            "siteidx": ScoringObject(
                self.main.scoringSiteidxLayerCombobox,
                self.main.scoringSiteidxThreshold1Spinbox,
                self.main.scoringSiteidxThreshold2Spinbox,
                "siteidx",
            ),
            "distance": ScoringObject(
                self.main.scoringDistanceLayerCombobox,
                self.main.scoringDistanceThreshold1Spinbox,
                self.main.scoringDistanceThreshold2Spinbox,
                "distance",
            ),
            "cost": ScoringObject(
                self.main.scoringCostLayerCombobox,
                self.main.scoringCostThreshold1Spinbox,
                self.main.scoringCostThreshold2Spinbox,
                "cost",
            ),
            "shc": ScoringObject(
                self.main.scoringShcLayerCombobox,
                self.main.scoringShcThreshold1Spinbox,
                self.main.scoringShcThreshold2Spinbox,
                "shc",
            ),
            "slope": ScoringObject(
                self.main.scoringSlopeLayerCombobox,
                self.main.scoringSlopeThreshold1Spinbox,
                self.main.scoringSlopeThreshold2Spinbox,
                "slope",
            ),
        }

        # レイヤー選択プルダウンをラスター限定に
        list(
            map(
                lambda obj: obj.combobox.setFilters(QgsMapLayerProxyModel.RasterLayer),
                self.scoring_objs_dict.values(),
            )
        )
        # 初期値セット
        list(
            map(
                self.init_scoring_rlayer_stats,
                self.scoring_objs_dict.values(),
            )
        )
        # comboboxのcurrentlayerが変わると、そのパラメタの閾値だけリセットされる
        list(
            map(
                lambda obj: obj.combobox.layerChanged.connect(
                    lambda _layer=None, obj=obj: self.init_scoring_rlayer_stats(obj)
                ),
                self.scoring_objs_dict.values(),
            )
        )

        # 更新ボタン
        self.main.scoringSiteidxStyleReloadPushbutton.clicked.connect(
            lambda: self.scoring_reload_thresholds(
                self.scoring_objs_dict.get("siteidx")
            )
        )
        self.main.scoringCostStyleReloadPushbutton.clicked.connect(
            lambda: self.scoring_reload_thresholds(self.scoring_objs_dict.get("cost"))
        )
        self.main.scoringDistanceStyleReloadPushbutton.clicked.connect(
            lambda: self.scoring_reload_thresholds(
                self.scoring_objs_dict.get("distance")
            )
        )
        self.main.scoringSlopeStyleReloadPushbutton.clicked.connect(
            lambda: self.scoring_reload_thresholds(self.scoring_objs_dict.get("slope"))
        )
        self.main.scoringShcStyleReloadPushbutton.clicked.connect(
            lambda: self.scoring_reload_thresholds(self.scoring_objs_dict.get("shc"))
        )

        # 統計値表示ボタン
        self.main.scoringSiteidxStatsButton.clicked.connect(
            lambda: self.show_scoring_rlayer_stats(
                self.scoring_objs_dict.get("siteidx")
            )
        )
        self.main.scoringCostStatsButton.clicked.connect(
            lambda: self.show_scoring_rlayer_stats(self.scoring_objs_dict.get("cost"))
        )
        self.main.scoringDistanceStatsButton.clicked.connect(
            lambda: self.show_scoring_rlayer_stats(
                self.scoring_objs_dict.get("distance")
            )
        )
        self.main.scoringSlopeStatsButton.clicked.connect(
            lambda: self.show_scoring_rlayer_stats(self.scoring_objs_dict.get("slope"))
        )
        self.main.scoringShcStatsButton.clicked.connect(
            lambda: self.show_scoring_rlayer_stats(self.scoring_objs_dict.get("shc"))
        )

        # Undoボタン
        self.main.scoringSiteidxStyleUndoPushbutton.clicked.connect(
            lambda: self.scoring_undo_thresholds(self.scoring_objs_dict.get("siteidx"))
        )
        self.main.scoringCostStyleUndoPushbutton.clicked.connect(
            lambda: self.scoring_undo_thresholds(self.scoring_objs_dict.get("cost"))
        )
        self.main.scoringDistanceStyleUndoPushbutton.clicked.connect(
            lambda: self.scoring_undo_thresholds(self.scoring_objs_dict.get("distance"))
        )
        self.main.scoringShcStyleUndoPushbutton.clicked.connect(
            lambda: self.scoring_undo_thresholds(self.scoring_objs_dict.get("shc"))
        )
        self.main.scoringSlopeStyleUndoPushbutton.clicked.connect(
            lambda: self.scoring_undo_thresholds(self.scoring_objs_dict.get("slope"))
        )

        # 初期値に戻すボタン
        self.main.scoringSiteidxStyleInitPushbutton.clicked.connect(
            lambda: self.back_to_initial_state(self.scoring_objs_dict.get("siteidx"))
        )
        self.main.scoringCostStyleInitPushbutton.clicked.connect(
            lambda: self.back_to_initial_state(self.scoring_objs_dict.get("cost"))
        )
        self.main.scoringDistanceStyleInitPushbutton.clicked.connect(
            lambda: self.back_to_initial_state(self.scoring_objs_dict.get("distance"))
        )
        self.main.scoringShcStyleInitPushbutton.clicked.connect(
            lambda: self.back_to_initial_state(self.scoring_objs_dict.get("shc"))
        )
        self.main.scoringSlopeStyleInitPushbutton.clicked.connect(
            lambda: self.back_to_initial_state(self.scoring_objs_dict.get("slope"))
        )

        # パラメタ読み込みボタン
        self.main.scoringReadParamsPushbutton.clicked.connect(self.readin_params_json)

        # UIの変更を検知しUI全体を更新する
        for signal in (
            self.main.scoringSiteidxLayerCombobox.layerChanged,
            self.main.scoringCostLayerCombobox.layerChanged,
            self.main.scoringDistanceLayerCombobox.layerChanged,
            self.main.scoringSlopeLayerCombobox.layerChanged,
            self.main.scoringShcLayerCombobox.layerChanged,
            self.main.scoringSaveareaLayerCombobox.layerChanged,
            self.main.scoringProfitGroupbox.toggled,
            self.main.scoringDisasterGroupbox.toggled,
            self.main.scoringOutputDirFileWidget.fileChanged,
        ):
            signal.connect(self.refresh_scoring_ui)

        self.refresh_scoring_ui()

    def readin_params_json(self):
        result = QFileDialog.getOpenFileNames(self.main, "ファイル選択", "", "params.json")
        if len(result[0]) == 0:
            # 未選択なら処理を終了
            return

        filepath = result[0][0]

        thresholds_dict = {}
        with open(filepath) as f:
            thresholds_dict = json.load(f)
        try:
            self.main.scoringSiteidxThreshold1Spinbox.setValue(
                thresholds_dict.get("siteidx")[0]
            )
            self.main.scoringSiteidxThreshold2Spinbox.setValue(
                thresholds_dict.get("siteidx")[1]
            )
            self.main.scoringCostThreshold1Spinbox.setValue(
                thresholds_dict.get("cost")[0]
            )
            self.main.scoringCostThreshold2Spinbox.setValue(
                thresholds_dict.get("cost")[1]
            )
            self.main.scoringDistanceThreshold1Spinbox.setValue(
                thresholds_dict.get("distance")[0]
            )
            self.main.scoringDistanceThreshold2Spinbox.setValue(
                thresholds_dict.get("distance")[1]
            )
            self.main.scoringShcThreshold1Spinbox.setValue(
                thresholds_dict.get("shc")[0]
            )
            self.main.scoringShcThreshold2Spinbox.setValue(
                thresholds_dict.get("shc")[1]
            )
            self.main.scoringSlopeThreshold1Spinbox.setValue(
                thresholds_dict.get("slope")[0]
            )
            self.main.scoringSlopeThreshold2Spinbox.setValue(
                thresholds_dict.get("slope")[1]
            )

            self._scoring_params_loaded = True
            for obj in self.scoring_objs_dict.values():
                obj.reset_threshold_history(
                    (obj.threshold1_spinbox.value(), obj.threshold2_spinbox.value())
                )
        except (TypeError, IndexError):
            QMessageBox.information(
                self.main, "エラー", "本プロクラムで生成したパラメータJSONファイルを選択してください。"
            )

    def set_scoring_layer_combobox(self):
        """MORIZON要素レイヤをスコアリング欄へ厳密に自動設定する。

        v2.1.9.5:
        ・表示名ではなく、原則として実ファイル名で各入力を識別する。
        ・Y_01/Y_02/Y_03/Y_11/Y_12/Y_13を別々に解決し、取り違えを防止する。
        ・_vN が存在する場合は基準ファイルより新しい世代を優先する。
        ・UI反映中はsignalを止め、QGIS側のlayerChanged連鎖による選択汚染を防ぐ。
        """
        project = QgsProject.instance()

        specs = [
            ("siteidx", self.main.scoringSiteidxLayerCombobox,
             [OUTPUT_SITEIDX_SUGI["FILE_NAME"], OUTPUT_SITEIDX_HINOKI["FILE_NAME"], OUTPUT_SITEIDX_KARAMATSU["FILE_NAME"]],
             [OUTPUT_SITEIDX_SUGI["DISPLAY_NAME"], OUTPUT_SITEIDX_HINOKI["DISPLAY_NAME"], OUTPUT_SITEIDX_KARAMATSU["DISPLAY_NAME"]]),
            ("cost", self.main.scoringCostLayerCombobox,
             [OUTPUT_COST["FILE_NAME"]], [OUTPUT_COST["DISPLAY_NAME"]]),
            ("distance", self.main.scoringDistanceLayerCombobox,
             [OUTPUT_DISTANCE["FILE_NAME"]], [OUTPUT_DISTANCE["DISPLAY_NAME"]]),
            ("shc", self.main.scoringShcLayerCombobox,
             [OUTPUT_SHC["FILE_NAME"]], [OUTPUT_SHC["DISPLAY_NAME"]]),
            ("slope", self.main.scoringSlopeLayerCombobox,
             [OUTPUT_SLOPE["FILE_NAME"]], [OUTPUT_SLOPE["DISPLAY_NAME"]]),
            ("savearea", self.main.scoringSaveareaLayerCombobox,
             [OUTPUT_SAVEAREA["FILE_NAME"]], [OUTPUT_SAVEAREA["DISPLAY_NAME"]]),
        ]

        def raster_layers():
            return [lyr for lyr in project.mapLayers().values()
                    if lyr is not None and lyr.type() == QgsMapLayer.RasterLayer]

        def source_path(layer):
            if layer is None:
                return ""
            try:
                value = layer.source()
                if value:
                    return value.split("|", 1)[0]
            except Exception:
                pass
            try:
                provider = layer.dataProvider()
                if provider is not None:
                    value = provider.dataSourceUri()
                    if value:
                        return value.split("|", 1)[0]
            except Exception:
                pass
            return ""

        def base_name(path):
            return os.path.splitext(os.path.basename(path))[0].lower()

        def match_generation(base, wanted):
            wanted = wanted.lower()
            if base == wanted:
                return 0
            m = re.fullmatch(re.escape(wanted) + r"_v([0-9]+)", base, re.I)
            return int(m.group(1)) if m else None

        # YOUSO候補フォルダを一度だけ確定する。
        dirs = []
        known = [
            "y_01_chii_sugi", "y_01_chii_hinoki", "y_01_chii_karamatsu",
            "y_02_shuzai", "y_03_chiri", "y_11_chikei", "y_12_keisha", "y_13_hozen"
        ]
        for lyr in raster_layers():
            path = source_path(lyr)
            if not path:
                continue
            b = base_name(path)
            if any(match_generation(b, k) is not None for k in known):
                d = os.path.dirname(os.path.abspath(path))
                if d and d not in dirs:
                    dirs.append(d)
        try:
            d = self.main.elementsOutputDirFileWidget.filePath()
            if d and os.path.isdir(d):
                d = os.path.abspath(d)
                if d not in dirs:
                    dirs.append(d)
        except Exception:
            pass

        def best_loaded(wanted):
            """指定した1種類だけを、source filenameで厳密に検索する。"""
            candidates = []
            for lyr in raster_layers():
                path = source_path(lyr)
                if not path:
                    continue
                gen = match_generation(base_name(path), wanted)
                if gen is not None:
                    candidates.append((gen, lyr))
            if not candidates:
                return None
            # _vNを優先。世代無しは0。
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
                    if not name.lower().endswith(".tif"):
                        continue
                    gen = match_generation(base_name(name), wanted)
                    if gen is not None:
                        candidates.append((gen, os.path.join(d, name)))
            if not candidates:
                return None
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]

        def resolve_one(wanted, display):
            lyr = best_loaded(wanted)
            if lyr is not None:
                return lyr
            path = best_file(wanted)
            if not path:
                return None
            lyr = QgsRasterLayer(path, display + "[スコアリング]")
            if not lyr.isValid():
                return None
            project.addMapLayer(lyr, True)
            return lyr

        resolved = []
        for key, combo, wanted_list, display_list in specs:
            layer = None
            # siteidxだけ Sugi -> Hinoki -> Karamatsu の順で採用。
            for i, wanted in enumerate(wanted_list):
                display = display_list[min(i, len(display_list) - 1)]
                layer = resolve_one(wanted, display)
                if layer is not None:
                    break
            resolved.append((key, combo, layer))

        # QGISのlayerChanged連鎖を完全に止めて一括反映する。
        blockers = [QSignalBlocker(combo) for _, combo, _ in resolved]
        try:
            for _, combo, layer in resolved:
                combo.setLayer(layer)
        finally:
            blockers.clear()

        # signalを止めたため必要なUI更新を明示する。
        # params.json を読み込んでいる場合は、その比較条件を保持する。
        if not getattr(self, "_scoring_params_loaded", False):
            for key in ("siteidx", "cost", "distance", "shc", "slope"):
                self.init_scoring_rlayer_stats(self.scoring_objs_dict[key])
        else:
            for obj in self.scoring_objs_dict.values():
                obj.reset_threshold_history(
                    (obj.threshold1_spinbox.value(), obj.threshold2_spinbox.value())
                )

        # QGISへディスクから自動ロードしたレイヤは既定のグレースケールに
        # なるため、現在のしきい値を使ってスコアリング色を必ず再適用する。
        # これは表示のみの変更で、計算値には影響しない。
        for key in ("siteidx", "cost", "distance", "shc", "slope"):
            obj = self.scoring_objs_dict[key]
            if obj.combobox.currentLayer() is not None:
                try:
                    self.set_scoring_raster_style(obj)
                except Exception:
                    pass

        # 保全対象は0/1のパレット表示を適用する。
        try:
            savearea_layer = self.main.scoringSaveareaLayerCombobox.currentLayer()
            if savearea_layer is not None:
                savearea_path = source_path(savearea_layer)
                savearea_dir = os.path.dirname(os.path.abspath(savearea_path)) if savearea_path else ""
                if savearea_dir:
                    qml = raster_styler.savearea.write_scoring_qml(savearea_dir)
                    savearea_layer.loadNamedStyle(qml)
                    iface.layerTreeView().refreshLayerSymbology(savearea_layer.id())
                    savearea_layer.triggerRepaint()
        except Exception:
            pass

        # 要素レイヤの保存先が .../YOUSO の場合、スコアリング出力は
        # 同じデータセット直下の .../ZONING を自動設定する。
        try:
            source_dirs = []
            for _, _, layer in resolved:
                path = source_path(layer)
                if path:
                    d = os.path.dirname(os.path.abspath(path))
                    if d not in source_dirs:
                        source_dirs.append(d)
            youso_dir = next(
                (d for d in source_dirs if os.path.basename(d).lower() == "youso"),
                source_dirs[0] if source_dirs else None
            )
            if youso_dir:
                zoning_dir = os.path.join(os.path.dirname(youso_dir), "ZONING")
                os.makedirs(zoning_dir, exist_ok=True)
                self.main.scoringOutputDirFileWidget.setFilePath(zoning_dir)
                if hasattr(self.main.scoringOutputDirFileWidget, "setDefaultRoot"):
                    self.main.scoringOutputDirFileWidget.setDefaultRoot(zoning_dir)
        except Exception:
            # 出力先自動設定に失敗しても手動指定は可能。
            pass

        self.refresh_scoring_ui()

    def refresh_scoring_ui(self):
        # 入力内容のエラーチェック
        error_texts = self.get_scoring_error_texts()
        self.main.scoringErrorLabel.setText("\n".join(error_texts))
        self.main.scoringRunPushButton.setEnabled(len(error_texts) == 0)

        # 各要素ごとのボタンの有効化チェック
        for combobox, stats_button, reload_button, undo_button, init_button, obj in (
            (
                self.main.scoringSiteidxLayerCombobox,
                self.main.scoringSiteidxStatsButton,
                self.main.scoringSiteidxStyleReloadPushbutton,
                self.main.scoringSiteidxStyleUndoPushbutton,
                self.main.scoringSiteidxStyleInitPushbutton,
                self.scoring_objs_dict["siteidx"],
            ),
            (
                self.main.scoringCostLayerCombobox,
                self.main.scoringCostStatsButton,
                self.main.scoringCostStyleReloadPushbutton,
                self.main.scoringCostStyleUndoPushbutton,
                self.main.scoringCostStyleInitPushbutton,
                self.scoring_objs_dict["cost"],
            ),
            (
                self.main.scoringDistanceLayerCombobox,
                self.main.scoringDistanceStatsButton,
                self.main.scoringDistanceStyleReloadPushbutton,
                self.main.scoringDistanceStyleUndoPushbutton,
                self.main.scoringDistanceStyleInitPushbutton,
                self.scoring_objs_dict["distance"],
            ),
            (
                self.main.scoringSlopeLayerCombobox,
                self.main.scoringSlopeStatsButton,
                self.main.scoringSlopeStyleReloadPushbutton,
                self.main.scoringSlopeStyleUndoPushbutton,
                self.main.scoringSlopeStyleInitPushbutton,
                self.scoring_objs_dict["slope"],
            ),
            (
                self.main.scoringShcLayerCombobox,
                self.main.scoringShcStatsButton,
                self.main.scoringShcStyleReloadPushbutton,
                self.main.scoringShcStyleUndoPushbutton,
                self.main.scoringShcStyleInitPushbutton,
                self.scoring_objs_dict["shc"],
            ),
        ):
            # まずすべてのUIを無効化する
            stats_button.setEnabled(False)
            reload_button.setEnabled(False)
            init_button.setEnabled(False)
            undo_button.setEnabled(False)

            # 使用可能なボタンのみ有効化する
            if combobox.currentLayer() is not None:
                is_valid = utils.is_valid_elements_layer(combobox.currentLayer())
                stats_button.setEnabled(is_valid)
                reload_button.setEnabled(is_valid)
                init_button.setEnabled(is_valid)
            if len(obj.threshold_history_list) > 1:
                undo_button.setEnabled(True)

    def set_scoring_raster_style(self, scoring_obj: ScoringObject):
        scores = scoring_obj.get_scores()
        scoring_colors = scoring_obj.get_scoring_colors()
        threshold1 = scoring_obj.threshold1_spinbox.value()
        threshold2 = scoring_obj.threshold2_spinbox.value()

        qml_filepath = write_qml_by_thresholds_and_colors(
            (threshold1, threshold2),
            scoring_colors,
            scores,
        )
        target_layer = scoring_obj.combobox.currentLayer()

        target_layer.loadNamedStyle(qml_filepath)
        iface.layerTreeView().refreshLayerSymbology(target_layer.id())  # レイヤー一覧の凡例を更新
        target_layer.setBlendMode(QPainter.CompositionMode_Multiply)  # 乗算に設定
        target_layer.triggerRepaint()  # キャンバス上の見た目を更新

    def scoring_reload_thresholds(self, scoring_obj: ScoringObject):
        """「更新」ボタンの動作"""
        self.set_scoring_raster_style(scoring_obj)

        # 更新した時点の閾値をScoringObjectに記録する
        threshold1 = scoring_obj.threshold1_spinbox.value()
        threshold2 = scoring_obj.threshold2_spinbox.value()
        scoring_obj.append_threshold_history([threshold1, threshold2])
        self.refresh_scoring_ui()

    def scoring_undo_thresholds(self, scoring_obj: ScoringObject):
        """
        「戻すボタン」の動作
        """
        if len(scoring_obj.threshold_history_list) < 2:
            # 履歴がなければ処理を終了
            return

        # 直前の閾値があればそれをspinboxにセットし、最新の閾値を削除する
        scoring_obj.threshold1_spinbox.setValue(
            scoring_obj.threshold_history_list[-2][0]
        )
        scoring_obj.threshold2_spinbox.setValue(
            scoring_obj.threshold_history_list[-2][1]
        )
        scoring_obj.threshold_history_list.pop(-1)

        self.set_scoring_raster_style(scoring_obj)
        self.refresh_scoring_ui()

    def show_scoring_rlayer_stats(self, scoring_obj: ScoringObject):
        self.main.hide()

        stats_dialog = ForestZoningScoringStatsDialog(
            scoring_obj.layer_name,
            scoring_obj.combobox.currentLayer(),
            scoring_obj.threshold1_spinbox.value(),
            scoring_obj.threshold2_spinbox.value(),
        )
        result = stats_dialog.exec_()

        if result == QDialog.Accepted:
            # しきい値をメイン画面で反映
            threshold1, threshold2 = stats_dialog.get_thresholds()
            scoring_obj.threshold1_spinbox.setValue(threshold1)
            scoring_obj.threshold2_spinbox.setValue(threshold2)
            self.set_scoring_raster_style(scoring_obj)

            scoring_obj.append_threshold_history([threshold1, threshold2])
            self.refresh_scoring_ui()

        self.main.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        self.main.show()

    def init_scoring_rlayer_stats(self, scoring_obj: ScoringObject):
        """レイヤがリセットされた時の挙動"""

        thresholds = get_initial_thresholds_of(scoring_obj)

        scoring_obj.threshold1_spinbox.setValue(thresholds[0])
        scoring_obj.threshold2_spinbox.setValue(thresholds[1])
        # scoring_objの履歴リストをリセットする
        scoring_obj.reset_threshold_history(thresholds)

    def back_to_initial_state(self, scoring_obj: ScoringObject):
        """「初期化に戻す」ボタンがクリックした時の挙動"""
        thresholds = get_initial_thresholds_of(scoring_obj)

        scoring_obj.threshold1_spinbox.setValue(thresholds[0])
        scoring_obj.threshold2_spinbox.setValue(thresholds[1])
        # ラスタスタイルを設定する
        self.set_scoring_raster_style(scoring_obj)
        # scoring_objの履歴リストに記録する
        scoring_obj.append_threshold_history(thresholds)
        self.refresh_scoring_ui()

    def set_scoring_score_labels_from_settings(self):
        smanager = SettingsManager()
        settings = smanager.get_settings()

        for scores, target_labels in (
            (
                settings["scores_siteidx"],
                (
                    self.main.scoringSiteidxScore1Label,
                    self.main.scoringSiteidxScore2Label,
                    self.main.scoringSiteidxScore3Label,
                ),
            ),
            (
                settings["scores_cost"],
                (
                    self.main.scoringCostScore1Label,
                    self.main.scoringCostScore2Label,
                    self.main.scoringCostScore3Label,
                ),
            ),
            (
                settings["scores_distance"],
                (
                    self.main.scoringDistanceScore1Label,
                    self.main.scoringDistanceScore2Label,
                    self.main.scoringDistanceScore3Label,
                ),
            ),
            (
                settings["scores_slope"],
                (
                    self.main.scoringSlopeScore1Label,
                    self.main.scoringSlopeScore2Label,
                    self.main.scoringSlopeScore3Label,
                ),
            ),
            (
                settings["scores_shc"],
                (
                    self.main.scoringShcScore1Label,
                    self.main.scoringShcScore2Label,
                    self.main.scoringShcScore3Label,
                ),
            ),
            (
                settings["scores_savearea"],
                (
                    self.main.scoringSaveareaScore1Label,
                    self.main.scoringSaveareaScore2Label,
                ),
            ),
        ):
            for idx, score in enumerate(scores):
                target_labels[idx].setText(str(score) + "点")

    def get_scoring_error_texts(self):
        error_texts = []

        for name, combobox in (
            ("地位", self.main.scoringSiteidxLayerCombobox),
            (OUTPUT_COST["DISPLAY_NAME"], self.main.scoringCostLayerCombobox),
            (
                OUTPUT_DISTANCE["DISPLAY_NAME"],
                self.main.scoringDistanceLayerCombobox,
            ),  # nopep8
            (OUTPUT_SLOPE["DISPLAY_NAME"], self.main.scoringSlopeLayerCombobox),
            (OUTPUT_SHC["DISPLAY_NAME"], self.main.scoringShcLayerCombobox),
            (
                OUTPUT_SAVEAREA["DISPLAY_NAME"],
                self.main.scoringSaveareaLayerCombobox,
            ),  # nopep8
        ):

            if not combobox.parent().isChecked():
                # 親カテゴリにチェックがないならエラー判定を行わない
                continue

            if combobox.currentLayer() is None:
                error_texts.append(f"{name}ラスターを指定してください")
                continue

            if combobox.currentLayer().type() != QgsMapLayer.RasterLayer:
                error_texts.append(f"{name}ラスターを指定してください")
                continue

            # 統計量をもとにした妥当性チェック
            if not utils.is_valid_elements_layer(combobox.currentLayer()):
                # ラスタータイルはここで引っかかる: MIN=1000000 MEAN=1000000 MAX=-10000 となるため
                error_texts.append(f"有効な{name}ラスターを指定してください")

                continue

            # MORIZON自身が生成した要素ラスタを別欄へ誤設定していないか確認する。
            # 任意の外部ラスタは妨げず、Y_01～Y_13の既知ファイル名だけを厳密判定する。
            try:
                base = os.path.splitext(os.path.basename(
                    combobox.currentLayer().dataProvider().dataSourceUri().split("|", 1)[0]
                ))[0].lower()
                base = re.sub(r"_v[0-9]+$", "", base)
                known = {
                    OUTPUT_SITEIDX_SUGI["FILE_NAME"].lower(),
                    OUTPUT_SITEIDX_HINOKI["FILE_NAME"].lower(),
                    OUTPUT_SITEIDX_KARAMATSU["FILE_NAME"].lower(),
                    OUTPUT_COST["FILE_NAME"].lower(),
                    OUTPUT_DISTANCE["FILE_NAME"].lower(),
                    OUTPUT_SLOPE["FILE_NAME"].lower(),
                    OUTPUT_SHC["FILE_NAME"].lower(),
                    OUTPUT_SAVEAREA["FILE_NAME"].lower(),
                }
                expected = {
                    "地位": {
                        OUTPUT_SITEIDX_SUGI["FILE_NAME"].lower(),
                        OUTPUT_SITEIDX_HINOKI["FILE_NAME"].lower(),
                        OUTPUT_SITEIDX_KARAMATSU["FILE_NAME"].lower(),
                    },
                    OUTPUT_COST["DISPLAY_NAME"]: {OUTPUT_COST["FILE_NAME"].lower()},
                    OUTPUT_DISTANCE["DISPLAY_NAME"]: {OUTPUT_DISTANCE["FILE_NAME"].lower()},
                    OUTPUT_SLOPE["DISPLAY_NAME"]: {OUTPUT_SLOPE["FILE_NAME"].lower()},
                    OUTPUT_SHC["DISPLAY_NAME"]: {OUTPUT_SHC["FILE_NAME"].lower()},
                    OUTPUT_SAVEAREA["DISPLAY_NAME"]: {OUTPUT_SAVEAREA["FILE_NAME"].lower()},
                }
                if base in known and base not in expected.get(name, set()):
                    error_texts.append(
                        f"{name}に別要素のMORIZONラスターが選択されています（{base}.tif）"
                    )
            except Exception:
                pass

        if (
            not self.main.scoringSiteidxLayerCombobox.parent().isChecked()
            and not self.main.scoringSlopeLayerCombobox.parent().isChecked()
        ):
            error_texts.append("「収益性軸」「災害リスク軸」のいずれかにひとつ以上にチェックしてください")

        if self.main.scoringOutputDirFileWidget.filePath() == "":
            error_texts.append("出力先フォルダを指定してください")

        return error_texts

    def scoring_get_existing_filenames(self):
        """
        「スコアリング」で、出力先フォルダに同名ファイルが存在するかチェック
        存在する場合そのすべてのファイル名の配列を返す

        Returns:
            list
        """
        output_dir = self.main.scoringOutputDirFileWidget.filePath()
        existing_filenames = []

        def append_filename_if_exist(file_info: dict):
            if os.path.exists(
                os.path.join(
                    output_dir, f"{file_info['FILE_NAME']}.{file_info['EXTENSION']}"
                )
            ):
                existing_filenames.append(
                    f"{file_info['FILE_NAME']}.{file_info['EXTENSION']}"
                )

        append_filename_if_exist(OUTPUT_PARAMS_JSON)
        if self.main.scoringSiteidxLayerCombobox.parent().isChecked():
            append_filename_if_exist(OUTPUT_PROFIT)
        if self.main.scoringSlopeLayerCombobox.parent().isChecked():
            append_filename_if_exist(OUTPUT_RISK)

        return existing_filenames

    def _remove_existing_scoring_results(self):
        """
        QGIS 3.44安定版:
        既存の「スコアリング」グループ内レイヤをプロジェクトから解除する。
        再計算のたびにユーザーがグループ名を変更/削除する必要をなくす。
        """
        project = QgsProject.instance()
        root = project.layerTreeRoot()

        # コンボボックスが既存shuekisei/saigairiskを保持していれば解除
        output_names = {
            OUTPUT_PROFIT["FILE_NAME"] + ".tif",
            OUTPUT_RISK["FILE_NAME"] + ".tif",
        }
        for combo in (
            self.main.scoringSiteidxLayerCombobox,
            self.main.scoringCostLayerCombobox,
            self.main.scoringDistanceLayerCombobox,
            self.main.scoringSlopeLayerCombobox,
            self.main.scoringShcLayerCombobox,
            self.main.scoringSaveareaLayerCombobox,
        ):
            try:
                lyr = combo.currentLayer()
                if lyr is not None:
                    src = os.path.basename(
                        lyr.dataProvider().dataSourceUri().split("|", 1)[0]
                    ).lower()
                    if src in output_names:
                        combo.setLayer(None)
            except Exception:
                pass

        # 「スコアリング」グループだけを対象にレイヤ削除
        for group in list(root.findGroups()):
            if group.name() != "スコアリング":
                continue
            ids = []
            for child in group.findLayers():
                try:
                    ids.append(child.layerId())
                except Exception:
                    pass
            if ids:
                project.removeMapLayers(ids)
            try:
                parent = group.parent()
                if parent is not None:
                    parent.removeChildNode(group)
            except Exception:
                pass

        QCoreApplication.processEvents()

    def run_scoring(self):
        existing_filenames = self.scoring_get_existing_filenames()
        if len(existing_filenames) > 0:
            if QMessageBox.No == QMessageBox.question(
                self.main,
                "上書き確認",
                "出力先フォルダに同名ファイルが存在します、上書きしますか？\n" + "\n".join(existing_filenames),
                QMessageBox.Yes,
                QMessageBox.No,
            ):
                QMessageBox.information(self.main, "処理中断", "処理を中断しました。")
                return

        # STEP8A: 既存スコアリング結果をQGISから自動解除して再計算可能にする
        self._remove_existing_scoring_results()

        input_layers_dict = {
            "siteidx": self.main.scoringSiteidxLayerCombobox.currentLayer(),
            "cost": self.main.scoringCostLayerCombobox.currentLayer(),
            "distance": self.main.scoringDistanceLayerCombobox.currentLayer(),
            "slope": self.main.scoringSlopeLayerCombobox.currentLayer(),
            "shc": self.main.scoringShcLayerCombobox.currentLayer(),
            "savearea": self.main.scoringSaveareaLayerCombobox.currentLayer(),
        }

        input_thresholds_dict = {
            "siteidx": (
                self.main.scoringSiteidxThreshold1Spinbox.value(),
                self.main.scoringSiteidxThreshold2Spinbox.value(),
            ),
            "cost": (
                self.main.scoringCostThreshold1Spinbox.value(),
                self.main.scoringCostThreshold2Spinbox.value(),
            ),
            "distance": (
                self.main.scoringDistanceThreshold1Spinbox.value(),
                self.main.scoringDistanceThreshold2Spinbox.value(),
            ),
            "slope": (
                self.main.scoringSlopeThreshold1Spinbox.value(),
                self.main.scoringSlopeThreshold2Spinbox.value(),
            ),
            "shc": (
                self.main.scoringShcThreshold1Spinbox.value(),
                self.main.scoringShcThreshold2Spinbox.value(),
            ),
        }

        # processingを実行する前にパラメタを書き出す
        params_filepath = os.path.join(
            self.main.scoringOutputDirFileWidget.filePath(), "params.json"
        )
        with open(params_filepath, "wt") as file:
            json.dump(input_thresholds_dict, file, ensure_ascii=False, indent=2)

        target_score_dict = {
            "profit": self.main.scoringSiteidxLayerCombobox.parent().isChecked(),
            "risk": self.main.scoringSlopeLayerCombobox.parent().isChecked(),
        }

        thread = processes.scoring.ProcessingThread(
            input_layers_dict,
            input_thresholds_dict,
            target_score_dict,
            self.main.scoringOutputDirFileWidget.filePath(),
        )
        progress_dialog = ProgressDialog(thread.set_abort_flag)
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
        """
        処理結果を受け取ってレイヤー群を1つのグループとしてプロジェクトに追加
        """
        root = QgsProject().instance().layerTreeRoot()
        group_node = root.insertGroup(0, "スコアリング")
        group_node.setExpanded(False)

        for rlayer in rlayers_dict.values():
            QgsProject.instance().addMapLayer(rlayer, False)
            group_node.addLayer(rlayer)
