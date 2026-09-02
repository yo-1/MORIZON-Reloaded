# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

import os
from qgis.core import QgsRasterLayer

from ...constants import OUTPUT_PROFIT, SCORING_COLORS_PROFIT
from .utils import (
    get_quantile_renderer,
    hex_to_rgb,
    write_qml_deviding_by_threshold,
    get_two_class_quantile_threshold_from_file,
)


def _quantile_threshold(filepath):
    # QGIS 3.44: renderer項目ではなく出力ラスターから表示用Quantileを取得
    return get_two_class_quantile_threshold_from_file(filepath)


def write_qml(profit_filepath: str, output_dir: str) -> str:
    threshold = _quantile_threshold(profit_filepath)
    return write_qml_deviding_by_threshold(
        threshold,
        SCORING_COLORS_PROFIT[0],
        SCORING_COLORS_PROFIT[1],
        os.path.join(output_dir, OUTPUT_PROFIT["FILE_NAME"] + ".qml"),
    )
