# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

"""Visual identity helpers for MORIZON Reloaded."""

import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon, QPixmap
from qgis.PyQt.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout


DISPLAY_NAME = "MORIZON Reloaded"
TAGLINE = "FOREST ZONING."
BUILD_LABEL = "UNOFFICIAL REVIVAL BUILD  /  QGIS 3.44  /  v2.3.0-rc2"


def asset_path(filename):
    return os.path.join(os.path.dirname(__file__), "imgs", filename)


def plugin_icon():
    return QIcon(asset_path("icon.png"))


def apply_window_branding(dialog, title=None, header=False):
    """Apply the identity without changing functional widget names."""
    dialog.setWindowTitle(title or DISPLAY_NAME)
    dialog.setWindowIcon(plugin_icon())
    dialog.setStyleSheet(_style_sheet())
    if header:
        _insert_header(dialog)


def _insert_header(dialog):
    root_layout = dialog.layout()
    if root_layout is None or dialog.findChild(QFrame, "reloadedHeader"):
        return

    header = QFrame(dialog)
    header.setObjectName("reloadedHeader")
    header.setMinimumHeight(82)
    layout = QHBoxLayout(header)
    layout.setContentsMargins(18, 10, 18, 10)
    layout.setSpacing(14)

    logo = QLabel(header)
    logo.setObjectName("reloadedLogo")
    logo.setFixedSize(58, 58)
    logo.setPixmap(
        QPixmap(asset_path("icon.png")).scaled(
            58, 58, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
    )
    layout.addWidget(logo)

    titles = QVBoxLayout()
    titles.setSpacing(0)
    name = QLabel(DISPLAY_NAME, header)
    name.setObjectName("reloadedTitle")
    tagline = QLabel(TAGLINE, header)
    tagline.setObjectName("reloadedTagline")
    build = QLabel(BUILD_LABEL, header)
    build.setObjectName("reloadedBuild")
    titles.addWidget(name)
    titles.addWidget(tagline)
    titles.addWidget(build)
    layout.addLayout(titles)
    layout.addStretch(1)

    status = QLabel("SYSTEM\nRELOADED", header)
    status.setObjectName("reloadedStatus")
    status.setAlignment(Qt.AlignCenter)
    layout.addWidget(status)
    root_layout.insertWidget(0, header)


def _style_sheet():
    return """
    QDialog { background: #f3f6f4; color: #17231d; }
    QFrame#reloadedHeader {
        background: #10231b; border: 1px solid #2d5946;
        border-radius: 7px;
    }
    QLabel#reloadedTitle { color: #ffffff; font-size: 24px; font-weight: 700; }
    QLabel#reloadedTagline {
        color: #5df2a5; font-size: 11px; font-weight: 700;
    }
    QLabel#reloadedBuild { color: #9db7aa; font-size: 9px; }
    QLabel#reloadedStatus {
        color: #5df2a5; background: #17392a; border: 1px solid #2a7252;
        border-radius: 4px; padding: 7px 13px; font-size: 9px;
        font-weight: 700;
    }
    QTabWidget::pane {
        border: 1px solid #bdc9c2; background: #ffffff; top: -1px;
    }
    QTabBar::tab {
        background: #e5ebe7; color: #31453a; border: 1px solid #bdc9c2;
        padding: 8px 17px; font-weight: 600;
    }
    QTabBar::tab:selected {
        background: #176b45; color: #ffffff; border-color: #176b45;
    }
    QGroupBox {
        border: 1px solid #c7d1cb; border-radius: 5px; margin-top: 10px;
        padding-top: 8px; font-weight: 600; background: #ffffff;
    }
    QGroupBox::title {
        subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #176b45;
    }
    QPushButton {
        background: #176b45; color: #ffffff; border: 1px solid #145c3c;
        border-radius: 4px; padding: 6px 12px; min-height: 20px;
        font-weight: 600;
    }
    QPushButton:hover { background: #21875a; }
    QPushButton:pressed { background: #0f5134; }
    QPushButton:disabled {
        background: #c7cfca; color: #7b8780; border-color: #b7c0ba;
    }
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
        background: #ffffff; border: 1px solid #aebbb3;
        border-radius: 3px; padding: 4px; selection-background-color: #176b45;
    }
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
        border: 1px solid #27a56c;
    }
    QProgressBar {
        border: 1px solid #9aaba1; border-radius: 4px;
        background: #e4eae6; text-align: center;
    }
    QProgressBar::chunk { background: #21b66f; }
    """
