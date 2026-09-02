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

PLUGIN_NAME = DISPLAY_NAME


class ForestZoning:
    def __init__(self, iface):
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
        for action in self.actions:
            self.iface.removePluginMenu(PLUGIN_NAME, action)
            self.iface.removeToolBarIcon(action)
        del self.toolbar

        QgsProject.instance().layerTreeRoot().addedChildren.disconnect(
            self.onLayersChanged
        )
        QgsProject.instance().layerTreeRoot().removedChildren.disconnect(
            self.onLayersChanged
        )
        self.iface.layerTreeView().layerTreeModel().dataChanged.connect(
            self.onLayersChanged
        )  # nopep8

    def onLayersChanged(self):
        if not self.is_visible_main_dialog():
            return

        self.main_dialog.elements.refresh_elements_ui()
        self.main_dialog.scoring.refresh_scoring_ui()
        self.main_dialog.zoning.refresh_zoning_ui()

    def show_main_dialog(self):
        if self.main_dialog is None:
            self.main_dialog = ForestZoningMainDialog()
            self.main_dialog.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
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
