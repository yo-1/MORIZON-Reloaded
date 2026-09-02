# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

import os

from osgeo import gdal
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg

# QGIS-API
from qgis.PyQt import uic
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import *
from .settings_manager import SettingsManager
from .branding import apply_window_branding


class QSeperatorSpinbox(QSpinBox):
    """
    カンマ区切り表示のためのQSpinBoxのサブクラス
    """

    def __init__(self, parent):
        super().__init__(parent)

        # UIの共通設定
        self.setSuffix("px")
        self.setMaximum(9999999)
        self.setButtonSymbols(QSpinBox.NoButtons)
        self.setMinimum(0)
        self.setReadOnly(True)

    def textFromValue(self, value: int):  # override
        return "{:,}".format(value)  # カンマ区切り


class ForestZoningScoringStatsDialog(QDialog):
    def __init__(
        self,
        layer_name: str,
        rlayer: QgsRasterLayer,
        threshold1: float,
        threshold2: float,
    ):
        super().__init__()
        self.ui = uic.loadUi(
            os.path.join(
                os.path.dirname(__file__), "forest_zoning_scoring_stats_dialog.ui"
            ),
            self,
        )
        apply_window_branding(self, "MORIZON Reloaded — スコア統計")

        # カンマ区切りのための独自のQSpinBoxクラス
        self.range1CountSpinbox = QSeperatorSpinbox(self)
        self.range1CountSpinbox.setPrefix("区間1: ")
        self.gridLayout_2.addWidget(self.range1CountSpinbox, 2, 1, 1, 2)
        self.range2CountSpinbox = QSeperatorSpinbox(self)
        self.range2CountSpinbox.setPrefix("区間2: ")
        self.gridLayout_2.addWidget(self.range2CountSpinbox, 2, 4, 1, 3)
        self.range3CountSpinbox = QSeperatorSpinbox(self)
        self.gridLayout_2.addWidget(self.range3CountSpinbox, 2, 8, 1, 2)
        self.range3CountSpinbox.setPrefix("区間3: ")

        self.layer_name = layer_name
        self.rlayer = rlayer

        # ラスターレイヤーをNumpyで読み込み
        gd = gdal.Open(rlayer.source())
        self.rlayer_array = gd.ReadAsArray()
        MIN_VALUE = 0  # 入力ラスター（スコアリング）の有効値は常に0以上
        self.rlayer_array = self.rlayer_array[MIN_VALUE <= self.rlayer_array]

        # グラフ周り初期化
        graph_fig = plt.figure()
        graph_fig.subplots_adjust(top=0.95, right=0.95, wspace=0, hspace=0)
        ax = graph_fig.add_subplot(1, 1, 1)
        # グラフの描画
        if self.layer_name == "cost":
            # 集材作業効率は離散値なのでヒストグラムの描画に工夫が必要
            ax.hist(
                self.rlayer_array,
                # fmt: off
                # 刻みを1ずつ、0~10で固定
                bins=[0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11],
                # fmt: on
                align="left",  # ラベルがbarの中心となるように
            )
        else:
            ax.hist(self.rlayer_array, bins=64)

        # しきい値の縦棒は後から更新するためクラス変数
        self.graph_threshold1 = ax.axvline(threshold1, color="r")
        self.graph_threshold2 = ax.axvline(threshold2, color="r")
        # ウィジェットを追加する
        self.graph_canvas = FigureCanvasQTAgg(graph_fig)
        self.graph_canvas.setFixedWidth(600)
        self.graph_canvas.setFixedHeight(400)
        self.graphAreaFrame.layout().addWidget(self.graph_canvas)

        # UIを初期化
        self.threshold1Spinbox.setValue(threshold1)
        self.threshold2Spinbox.setValue(threshold2)
        self.init_ui()

    def get_thresholds_for_graph(self):
        threshold1 = self.threshold1Spinbox.value()
        threshold2 = self.threshold2Spinbox.value()

        if self.layer_name == "cost":
            # 集材作業効率は整数の離散値なのでグラフ上の見た目を整えるためにしきい値の縦棒を1/2だけ右方シフトする
            threshold1 += 0.5
            threshold2 += 0.5

        return threshold1, threshold2

    def init_ui(self):
        self.layernameLabel.setText(self.rlayer.name())
        self.okButton.clicked.connect(self.accept)
        self.cancelButton.clicked.connect(self.reject)

        if self.layer_name == "shc":  # SHCは値の刻みを細かく
            self.threshold1Spinbox.setSingleStep(0.001)
            self.threshold2Spinbox.setSingleStep(0.001)
        elif self.layer_name == "cost":  # 集材作業効率は整数単位
            self.threshold1Spinbox.setSingleStep(1.0)
            self.threshold2Spinbox.setSingleStep(1.0)

        smanager = SettingsManager()
        settings = smanager.get_settings()
        scores = settings[f"scores_{self.layer_name}"]
        self.thresholdScore1Label.setText(str(scores[0]))
        self.thresholdScore2Label.setText(str(scores[1]))
        self.thresholdScore3Label.setText(str(scores[2]))

        rlayer_stats = {
            "MIN": np.min(self.rlayer_array),
            "MAX": np.max(self.rlayer_array),
            "MEAN": np.average(self.rlayer_array),
            "MEDIAN": np.median(self.rlayer_array),
        }
        self.minSpinbox.setValue(rlayer_stats["MIN"])
        self.maxSpinbox.setValue(rlayer_stats["MAX"])
        self.meanSpinbox.setValue(rlayer_stats["MEAN"])
        self.medianSpinbox.setValue(rlayer_stats["MEDIAN"])

        # しきい値入力時にグラフとピクセル数を再計算
        self.threshold1Spinbox.valueChanged.connect(self.redraw_graph)
        self.threshold2Spinbox.valueChanged.connect(self.redraw_graph)
        self.threshold1Spinbox.valueChanged.connect(self.calculate_pixel_counts)
        self.threshold2Spinbox.valueChanged.connect(self.calculate_pixel_counts)

        self.redraw_graph()
        self.calculate_pixel_counts()

    def redraw_graph(self):
        """
        グラフの表示を更新する
        """
        threshold1, threshold2 = self.get_thresholds_for_graph()
        # しきい値の縦棒
        self.graph_threshold1.set_xdata(threshold1)
        self.graph_threshold2.set_xdata(threshold2)

        self.graph_canvas.draw()

    def calculate_pixel_counts(self):
        """
        入力されたしきい値をもとに区間ごとのピクセル数を計算・表示する
        """
        range1_array = self.rlayer_array[
            self.rlayer_array <= self.threshold1Spinbox.value()
        ]
        range2_array = self.rlayer_array[
            (self.threshold1Spinbox.value() < self.rlayer_array)
            & (self.rlayer_array <= self.threshold2Spinbox.value())
        ]
        range3_array = self.rlayer_array[
            self.threshold2Spinbox.value() < self.rlayer_array
        ]

        self.range1CountSpinbox.setValue(len(range1_array))
        self.range1CountSpinbox.setSuffix(
            "px ({:.2%})".format(len(range1_array) / len(self.rlayer_array))
        )
        self.range2CountSpinbox.setValue(len(range2_array))
        self.range2CountSpinbox.setSuffix(
            "px ({:.2%})".format(len(range2_array) / len(self.rlayer_array))
        )
        self.range3CountSpinbox.setValue(len(range3_array))
        self.range3CountSpinbox.setSuffix(
            "px ({:.2%})".format(len(range3_array) / len(self.rlayer_array))
        )

    def get_thresholds(self):
        return (self.threshold1Spinbox.value(), self.threshold2Spinbox.value())
