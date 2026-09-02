# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

import os

from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog

from .forest_zoning_main_dialog_elements import ForestZoningMainDialogElements
from .forest_zoning_main_dialog_scoring import ForestZoningMainDialogScoring
from .forest_zoning_main_dialog_zoning import ForestZoningMainDialogZoning
from .forest_zoning_main_dialog_aggregate import ForestZoningMainDialogAggregate
from .forest_zoning_main_dialog_printlayout import ForestZoningMainDialogPrintlayout
from .branding import apply_window_branding


class ForestZoningMainDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.ui = uic.loadUi(
            os.path.join(os.path.dirname(__file__), "forest_zoning_main_dialog.ui"),
            self,
        )
        apply_window_branding(self, header=True)

        # 各タブのUIを初期化する：実装は各クラスへ移譲
        self.elements = ForestZoningMainDialogElements(self)
        self.scoring = ForestZoningMainDialogScoring(self)
        self.zoning = ForestZoningMainDialogZoning(self)
        self.aggregate = ForestZoningMainDialogAggregate(self)
        self.printlayout = ForestZoningMainDialogPrintlayout(self)
