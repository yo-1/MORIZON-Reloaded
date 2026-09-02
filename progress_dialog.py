# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

import os

# QGIS-API
from qgis.PyQt import uic
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import *
from .branding import apply_window_branding


class ProgressDialog(QDialog):
    def __init__(self, set_abort_flag_callback):
        super().__init__()
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.ui = uic.loadUi(
            os.path.join(os.path.dirname(__file__), "progress_dialog.ui"), self
        )
        apply_window_branding(self, "MORIZON Reloaded — PROCESSING")

        self.set_abort_flag_callback = set_abort_flag_callback
        self.init_ui()

    def init_ui(self):
        self.label.setText("処理開始中...")
        self.progressBar.setValue(0)
        self.progressBar.setMaximum(0)
        self.abortButton.setEnabled(True)
        self.abortButton.setText("中断")
        self.abortButton.clicked.connect(self.on_abort_click)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            return
        super().keyPressEvent(event)

    def on_abort_click(self):
        if QMessageBox.Yes == QMessageBox.question(
            self, "確認", "処理を中断し、以降の処理をスキップしてよろしいですか？", QMessageBox.Yes, QMessageBox.No
        ):
            if self.abortButton.isEnabled():  # 中断可能な場合のみ中断イベントを発火させる
                self.set_abort_flag_callback(True)
                self.abortButton.setEnabled(False)
                self.abortButton.setText("中断待機中...")

    def set_sum_of_processes(self, value: int):
        self.progressBar.setMaximum(value)

    def add_progress(self, value: int):
        self.progressBar.setValue(self.progressBar.value() + value)

    def set_messsage(self, message: str):
        self.label.setText(message + "...")

    def set_abortable(self, abortable=True):
        self.abortButton.setEnabled(abortable)
