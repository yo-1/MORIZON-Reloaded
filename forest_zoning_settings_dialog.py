# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

import os
import json

# QGIS-API
from qgis.PyQt import uic
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import *


from .settings_manager import SettingsManager, DEFAULT_SETTINGS
from .branding import apply_window_branding


class ForestZoningSettingsDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.ui = uic.loadUi(os.path.join(os.path.dirname(
            __file__), 'forest_zoning_settings_dialog.ui'), self)
        apply_window_branding(self, "MORIZON Reloaded — 設定")
        self.init_ui()

    def init_ui(self):
        self.storeSettingsPushButton.clicked.connect(self.store_settings)
        self.abortSettingsPushButton.clicked.connect(self.close)
        self.restoreDefaultSettingsPushButton.clicked.connect(
            self.restore_default_settings)
        self.writeFilePushbutton.clicked.connect(self.write_settings_to_file)
        self.readFilePushbutton.clicked.connect(self.read_settings_from_file)

        self.settingsRuggednessSpinbox.valueChanged.connect(
            lambda: self.force_odd(self.settingsRuggednessSpinbox))
        self.settingsShcSpinbox.valueChanged.connect(
            lambda: self.force_odd(self.settingsShcSpinbox))

        self.set_values_from_stored_settings()

    @staticmethod
    def force_odd(spinbox):
        """
        Spinboxの値を強制的に奇数にする
        """
        if spinbox.value() % 2 == 0:
            spinbox.setValue(
                min(spinbox.maximum(), max(spinbox.minimum(), spinbox.value() - 1)))

    def set_ui_values(self, settings: dict):
        self.settingsSiteidxScore1Spinbox.setValue(
            int(settings["scores_siteidx"][0]))
        self.settingsSiteidxScore2Spinbox.setValue(
            int(settings["scores_siteidx"][1]))
        self.settingsSiteidxScore3Spinbox.setValue(
            int(settings["scores_siteidx"][2]))
        self.settingsCostScore1Spinbox.setValue(
            int(settings["scores_cost"][0]))
        self.settingsCostScore2Spinbox.setValue(
            int(settings["scores_cost"][1]))
        self.settingsCostScore3Spinbox.setValue(
            int(settings["scores_cost"][2]))
        self.settingsDistanceScore1Spinbox.setValue(
            int(settings["scores_distance"][0]))
        self.settingsDistanceScore2Spinbox.setValue(
            int(settings["scores_distance"][1]))
        self.settingsDistanceScore3Spinbox.setValue(
            int(settings["scores_distance"][2]))
        self.settingsShcScore1Spinbox.setValue(
            int(settings["scores_shc"][0]))
        self.settingsShcScore2Spinbox.setValue(
            int(settings["scores_shc"][1]))
        self.settingsShcScore3Spinbox.setValue(
            int(settings["scores_shc"][2]))
        self.settingsSlopeScore1Spinbox.setValue(
            int(settings["scores_slope"][0]))
        self.settingsSlopeScore2Spinbox.setValue(
            int(settings["scores_slope"][1]))
        self.settingsSlopeScore3Spinbox.setValue(
            int(settings["scores_slope"][2]))
        self.settingsSaveareaScore1Spinbox.setValue(
            int(settings["scores_savearea"][0]))
        self.settingsSaveareaScore2Spinbox.setValue(
            int(settings["scores_savearea"][1]))
        self.settingsSiteidxSugiBaseSpinbox.setValue(
            float(settings["siteidx_sugi_params"][0]))
        self.settingsSiteidxSugiNpp1Spinbox.setValue(
            float(settings["siteidx_sugi_params"][1]))
        self.settingsSiteidxSugiNpp2Spinbox.setValue(
            float(settings["siteidx_sugi_params"][2]))
        self.settingsSiteidxSugiSrad1Spinbox.setValue(
            float(settings["siteidx_sugi_params"][3]))
        self.settingsSiteidxSugiSrad2Spinbox.setValue(
            float(settings["siteidx_sugi_params"][4]))
        self.settingsSiteidxSugiVtex1Spinbox.setValue(
            float(settings["siteidx_sugi_params"][5]))
        self.settingsSiteidxSugiVtex2Spinbox.setValue(
            float(settings["siteidx_sugi_params"][6]))
        self.settingsSiteidxHinokiBaseSpinbox.setValue(
            float(settings["siteidx_hinoki_params"][0]))
        self.settingsSiteidxHinokiNpp1Spinbox.setValue(
            float(settings["siteidx_hinoki_params"][1]))
        self.settingsSiteidxHinokiNpp2Spinbox.setValue(
            float(settings["siteidx_hinoki_params"][2]))
        self.settingsSiteidxHinokiSrad1Spinbox.setValue(
            float(settings["siteidx_hinoki_params"][3]))
        self.settingsSiteidxHinokiSrad2Spinbox.setValue(
            float(settings["siteidx_hinoki_params"][4]))
        self.settingsSiteidxHinokiVtex1Spinbox.setValue(
            float(settings["siteidx_hinoki_params"][5]))
        self.settingsSiteidxHinokiVtex2Spinbox.setValue(
            float(settings["siteidx_hinoki_params"][6]))
        self.settingsSiteidxKaramatsuBaseSpinbox.setValue(
            float(settings["siteidx_karamatsu_params"][0]))
        self.settingsSiteidxKaramatsuNpp1Spinbox.setValue(
            float(settings["siteidx_karamatsu_params"][1]))
        self.settingsSiteidxKaramatsuNpp2Spinbox.setValue(
            float(settings["siteidx_karamatsu_params"][2]))
        self.settingsSiteidxKaramatsuSrad1Spinbox.setValue(
            float(settings["siteidx_karamatsu_params"][3]))
        self.settingsSiteidxKaramatsuSrad2Spinbox.setValue(
            float(settings["siteidx_karamatsu_params"][4]))
        self.settingsSiteidxKaramatsuVtex1Spinbox.setValue(
            float(settings["siteidx_karamatsu_params"][5]))
        self.settingsSiteidxKaramatsuVtex2Spinbox.setValue(
            float(settings["siteidx_karamatsu_params"][6]))
        self.settingsRuggednessSpinbox.setValue(
            int(float(settings["ruggedness_param"])))
        self.settingsShcSpinbox.setValue(int(float(settings["shc_param"])))

        if settings["cost_algorithm"] == "ruggedness":
            self.costAlgoRuggednessRadio.setChecked(True) # 起伏量
        else:
            self.costAlgoShcRadio.setChecked(True) # SHC

    def set_values_from_stored_settings(self):
        smanager = SettingsManager()
        settings = smanager.get_settings()
        self.set_ui_values(settings)

    def restore_default_settings(self):
        answer = QMessageBox.question(self,
                                      "",
                                      "全ての設定値を初期化してよろしいですか？",
                                      QMessageBox.Yes | QMessageBox.No)

        if answer == QMessageBox.No:
            return

        smanager = SettingsManager()
        smanager.restore_default_settings()
        self.set_values_from_stored_settings()
        QMessageBox.information(self, "完了", "初期設定を復元しました")
        self.close()

    def make_settings_dict(self):
        scores_siteidx = [
            self.settingsSiteidxScore1Spinbox.value(),
            self.settingsSiteidxScore2Spinbox.value(),
            self.settingsSiteidxScore3Spinbox.value(),
        ]
        scores_cost = [
            self.settingsCostScore1Spinbox.value(),
            self.settingsCostScore2Spinbox.value(),
            self.settingsCostScore3Spinbox.value(),
        ]
        scores_distance = [
            self.settingsDistanceScore1Spinbox.value(),
            self.settingsDistanceScore2Spinbox.value(),
            self.settingsDistanceScore3Spinbox.value(),
        ]
        scores_shc = [
            self.settingsShcScore1Spinbox.value(),
            self.settingsShcScore2Spinbox.value(),
            self.settingsShcScore3Spinbox.value(),
        ]
        scores_slope = [
            self.settingsSlopeScore1Spinbox.value(),
            self.settingsSlopeScore2Spinbox.value(),
            self.settingsSlopeScore3Spinbox.value(),
        ]
        scores_savearea = [
            self.settingsSaveareaScore1Spinbox.value(),
            self.settingsSaveareaScore2Spinbox.value()
        ]

        digits = 5  # 小数点桁丸め

        return {
            "scores_siteidx": scores_siteidx,
            "scores_cost": scores_cost,
            "scores_distance": scores_distance,
            "scores_shc": scores_shc,
            "scores_slope": scores_slope,
            "scores_savearea": scores_savearea,
            "siteidx_sugi_params": [
                round(self.settingsSiteidxSugiBaseSpinbox.value(), digits),
                round(self.settingsSiteidxSugiNpp1Spinbox.value(), digits),
                round(self.settingsSiteidxSugiNpp2Spinbox.value(), digits),
                round(self.settingsSiteidxSugiSrad1Spinbox.value(), digits),
                round(self.settingsSiteidxSugiSrad2Spinbox.value(), digits),
                round(self.settingsSiteidxSugiVtex1Spinbox.value(), digits),
                round(self.settingsSiteidxSugiVtex2Spinbox.value(), digits)],
            "siteidx_hinoki_params": [
                round(self.settingsSiteidxHinokiBaseSpinbox.value(), digits),
                round(self.settingsSiteidxHinokiNpp1Spinbox.value(), digits),
                round(self.settingsSiteidxHinokiNpp2Spinbox.value(), digits),
                round(self.settingsSiteidxHinokiSrad1Spinbox.value(), digits),
                round(self.settingsSiteidxHinokiSrad2Spinbox.value(), digits),
                round(self.settingsSiteidxHinokiVtex1Spinbox.value(), digits),
                round(self.settingsSiteidxHinokiVtex2Spinbox.value(), digits)],
            "siteidx_karamatsu_params": [
                round(self.settingsSiteidxKaramatsuBaseSpinbox.value(), digits),
                round(self.settingsSiteidxKaramatsuNpp1Spinbox.value(), digits),
                round(self.settingsSiteidxKaramatsuNpp2Spinbox.value(), digits),
                round(self.settingsSiteidxKaramatsuSrad1Spinbox.value(), digits),
                round(self.settingsSiteidxKaramatsuSrad2Spinbox.value(), digits),
                round(self.settingsSiteidxKaramatsuVtex1Spinbox.value(), digits),
                round(self.settingsSiteidxKaramatsuVtex2Spinbox.value(), digits)],
            "ruggedness_param": self.settingsRuggednessSpinbox.value(),
            "shc_param": self.settingsShcSpinbox.value(),
            "cost_algorithm": "ruggedness" if self.costAlgoRuggednessRadio.isChecked() else "shc"
        }

    def store_settings(self):
        smanager = SettingsManager()
        new_settings = self.make_settings_dict()
        smanager.store_settings(new_settings)
        QMessageBox.information(None, "完了", "設定を保存しました")
        self.close()

    def write_settings_to_file(self):
        current_settings = self.make_settings_dict()
        output_filepath = QFileDialog.getSaveFileName(self,
                                                      "設定ファイルの保存先を選択",
                                                      "settings.json",
                                                      "*.json")[0]

        if output_filepath == "":
            return

        with open(output_filepath, mode='w') as f:
            json.dump(current_settings, f, indent=2)

        QMessageBox.information(None, "完了", "設定ファイルを保存しました")

    def read_settings_from_file(self):
        settings_filepath = QFileDialog.getOpenFileName(self,
                                                        "設定ファイルを選択",
                                                        None,
                                                        "*.json")[0]

        if settings_filepath == "":
            return

        try:
            with open(settings_filepath) as f:
                settings_json = json.load(f)
        except Exception as e:
            QMessageBox.information(
                None, "エラー", f"設定ファイルが正しいJSON形式ではありません\n{e}")
            return

        new_settings = DEFAULT_SETTINGS()
        # バリデーションに通った値だけデフォルト設定値に対して上書き（通常はすべての値が上書きされる）
        for key in DEFAULT_SETTINGS().keys():
            if settings_json.get(key) is not None:
                if SettingsManager.validate_setting(key, settings_json[key]) is None:
                    new_settings[key] = settings_json[key]

        self.set_ui_values(new_settings)
        QMessageBox.information(None, "完了", "設定ファイルを読み込みました\nまだ保存はされていません")
