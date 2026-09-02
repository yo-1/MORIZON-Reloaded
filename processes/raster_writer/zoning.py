# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

import os

from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import *
from qgis.analysis import QgsRasterCalculator, QgsRasterCalculatorEntry

from ...constants import OUTPUT_ZONING


def generate(profit_rlayer: QgsRasterLayer,
             profit_threshold: int,
             risk_rlayer: QgsRasterLayer,
             risk_threshold: int,
             output_dir: str) -> str:
    """
    ゾーニング図を生成する

    Args:
        profit_rlayer (QgsRasterLayer)
        profit_threshold (int)
        risk_rlayer (QgsRasterLayer)
        risk_threshold (int)
        output_dir (str)

    Returns:
        str: 生成したファイルの絶対パス
    """
    # ラスター計算のためにEntry生成
    profit_entry = QgsRasterCalculatorEntry()
    profit_entry.ref = "profit@1"
    profit_entry.raster = profit_rlayer
    profit_entry.bandNumber = 1

    risk_entry = QgsRasterCalculatorEntry()
    risk_entry.ref = "risk@1"
    risk_entry.raster = risk_rlayer
    risk_entry.bandNumber = 1

    os.makedirs(output_dir, exist_ok=True)

    base_filepath = os.path.join(
        output_dir,
        OUTPUT_ZONING["FILE_NAME"] + "." + OUTPUT_ZONING["EXTENSION"]
    )

    # 既存成果は削除・上書きしない。QGIS/Windowsが参照中でも安全に再実行できるよう
    # zoning_v2.tif, zoning_v3.tif ... と世代保存する。
    if not os.path.exists(base_filepath):
        output_filepath = base_filepath
    else:
        version = 2
        while True:
            candidate = os.path.join(
                output_dir,
                f"{OUTPUT_ZONING['FILE_NAME']}_v{version}.{OUTPUT_ZONING['EXTENSION']}"
            )
            if not os.path.exists(candidate):
                output_filepath = candidate
                break
            version += 1

    expression = _make_expression(profit_entry.ref, profit_threshold,
                                  risk_entry.ref, risk_threshold)

    calc = QgsRasterCalculator(expression,
                               output_filepath,
                               "GTiff",
                               profit_rlayer.extent(),
                               profit_rlayer.width(),
                               profit_rlayer.height(),
                               (profit_entry, risk_entry))
    calc.processCalculation()

    return output_filepath


def _make_expression(profit_name: str, profit_threshold: int,
                     risk_name: str, risk_threshold: int) -> str:
    """
    ゾーニングを計算するためのExpression式を生成する

    計算の考え方

    x軸: RISKの値
    y軸: PROFITの値

    上記2軸からなるxy平面を、しきい値により下図4象限に区分し、2つのラスターをその象限の値に畳み込む（1~4の値になる）
     _________
    |  2 |  1 |
    |____|____|
    |  3 |  4 |
    |____|____|
    """
    return f"""
    1 * ({profit_threshold} < {profit_name} AND {risk_threshold} < {risk_name})
    + 2 * ({profit_threshold} < {profit_name} AND {risk_name} <= {risk_threshold})
    + 3 * ({profit_name} <= {profit_threshold} AND {risk_name} <= {risk_threshold})
    + 4 * ({profit_name} <= {profit_threshold} AND {risk_threshold} < {risk_name})
    """
