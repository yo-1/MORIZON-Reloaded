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

from .forest_zoning_main_dialog import ForestZoningMainDialog
from .forest_zoning_settings_dialog import ForestZoningSettingsDialog
from .branding import DISPLAY_NAME, asset_path
from .diag_log import (
    UiStallWatchdog,
    count_event,
    register_dialog_visibility_check,
    timed,
)

PLUGIN_NAME = DISPLAY_NAME


class ForestZoning:
    def __init__(self, iface):
        # 診断用: プラグイン本体の構築（QGIS起動時）が重なる形で
        # 起動直後にUI停止が記録される事例があり（O-15、原因未特定）、
        # MORIZON自身の処理かどうかを切り分けるために計測する。
        with timed("プラグイン初期化: __init__"):
            self.iface = iface
            self.win = self.iface.mainWindow()
            self.plugin_dir = os.path.dirname(__file__)
            self.actions = []
            self.menu = PLUGIN_NAME
            self.toolbar = self.iface.addToolBar(PLUGIN_NAME)
            self.toolbar.setObjectName(PLUGIN_NAME)

            self.main_dialog = None
            self.settings_dialog = None

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None,
    ):
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)
        if status_tip is not None:
            action.setStatusTip(status_tip)
        if whats_this is not None:
            action.setWhatsThis(whats_this)
        if add_to_toolbar:
            self.toolbar.addAction(action)
        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)
        self.actions.append(action)
        return action

    def initGui(self):
        # 診断用: initGui自体の所要時間を計測する（O-15、起動直後のUI停止の
        # 切り分け用）。ウォッチドッグのQTimerはQtのイベントループに制御が
        # 戻るまで発火できないため、ここが遅い場合は次のtick時に重なった
        # 区間として記録される。速くても、起動直後の停止がMORIZON外の処理
        # によるものと判断する手がかりになる。
        with timed("プラグイン初期化: initGui"):
            # UIスレッドの停止(応答なし)を検知して MORIZON タブへ記録する
            self._stall_watchdog = UiStallWatchdog()
            self._stall_watchdog.start()
            # dev9: MORIZONのメインダイアログが開いているかどうかを
            # ウォッチドッグから参照できるよう登録する（Info/Warning判定用）
            register_dialog_visibility_check(self.is_visible_main_dialog)

            # メニュー設定
            self.add_action(
                icon_path=asset_path("icon.png"),
                text="MORIZON Reloaded を起動",
                callback=self.show_main_dialog,
                parent=self.win,
            )
            self.add_action(
                icon_path=asset_path("icon.png"),
                text="MORIZON Reloaded 設定",
                callback=self.show_settings_dialog,
                add_to_toolbar=False,
                parent=self.win,
            )

            QgsProject.instance().layerTreeRoot().addedChildren.connect(
                self.onLayersChanged
            )
            QgsProject.instance().layerTreeRoot().removedChildren.connect(
                self.onLayersChanged
            )
            self.iface.layerTreeView().layerTreeModel().dataChanged.connect(
                self.onLayersChanged
            )  # nopep8

    def unload(self):
        watchdog = getattr(self, "_stall_watchdog", None)
        if watchdog is not None:
            watchdog.stop()

        for action in self.actions:
            self.iface.removePluginMenu(PLUGIN_NAME, action)
            self.toolbar.removeAction(action)
        self.actions.clear()
        self.iface.mainWindow().removeToolBar(self.toolbar)
        self.toolbar.deleteLater()

        QgsProject.instance().layerTreeRoot().addedChildren.disconnect(
            self.onLayersChanged
        )
        QgsProject.instance().layerTreeRoot().removedChildren.disconnect(
            self.onLayersChanged
        )
        self.iface.layerTreeView().layerTreeModel().dataChanged.disconnect(
            self.onLayersChanged
        )  # nopep8

    def onLayersChanged(self):
        if not self.is_visible_main_dialog():
            return

        # 診断用: レイヤーツリーの変更（dataChangedは高頻度で発火する）の度に
        # 3画面のUI更新が走る。回数と、遅かった場合の所要時間を記録する。
        count_event("onLayersChanged")
        with timed("onLayersChanged: 要素UI更新", min_seconds=0.3):
            self.main_dialog.elements.refresh_elements_ui()
        with timed("onLayersChanged: スコアリングUI更新", min_seconds=0.3):
            self.main_dialog.scoring.refresh_scoring_ui()
        with timed("onLayersChanged: ゾーニングUI更新", min_seconds=0.3):
            self.main_dialog.zoning.refresh_zoning_ui()

    def show_main_dialog(self):
        if self.main_dialog is None:
            with timed("メイン画面の生成"):
                self.main_dialog = ForestZoningMainDialog()
            self.main_dialog.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        with timed("メイン画面の表示", min_seconds=0.3):
            self.main_dialog.show()

    def is_visible_main_dialog(self):
        if self.main_dialog is None:
            return False
        return self.main_dialog.isVisible()

    def show_settings_dialog(self):
        if self.settings_dialog is None:
            self.settings_dialog = ForestZoningSettingsDialog()
        else:
            self.settings_dialog.__init__()

        # メイン画面の表示状態を保存
        if self.is_visible_main_dialog():
            # 設定画面を開く前にメイン画面が開かれていたなら
            # 設定画面を開くときにメイン画面を不可視にして
            # 設定画面を閉じるときに再表示し新しい設定値を読み込み
            self.main_dialog.hide()
            self.settings_dialog.exec()
            self.main_dialog.show()
            self.main_dialog.scoring.set_scoring_score_labels_from_settings()
        else:
            self.settings_dialog.exec()
