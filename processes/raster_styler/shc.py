# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

import os
import tempfile

from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import *

from ...constants import (
    OUTPUT_SHC,
    SCORING_COLORS_SHC,
    RAWDATA_COLORS_SHC
)
from .utils import (
    get_quantile_renderer,
    hex_to_rgb,
    replace_colorramp_labels,
    get_colorramp_label_prefixes,
    round_label_precision
)


def write_rawdata_qml(shc_filepath: str, output_dir: str) -> str:
    rlayer = QgsRasterLayer(shc_filepath, '')
    colors = list(map(hex_to_rgb, RAWDATA_COLORS_SHC))
    renderer = get_quantile_renderer(rlayer, colors)
    renderer.setOpacity(0.8)
    rlayer.setRenderer(renderer)
    rlayer.setBlendMode(QPainter.CompositionMode_Multiply)
    rlayer.setContrastEnhancement(QgsContrastEnhancement.StretchToMinimumMaximum,
                                  QgsRasterMinMaxOrigin.MinMax)

    with tempfile.NamedTemporaryFile(delete=False, suffix='.qml') as temp_qml:
        rlayer.saveNamedStyle(temp_qml.name)
        output_filepath = round_label_precision(temp_qml.name,
                                                os.path.join(
                                                    output_dir, OUTPUT_SHC["FILE_NAME"] + '_raw.qml'),
                                                precision=4)
    return output_filepath


def write_scoring_qml(shc_filepath: str, output_dir: str) -> str:
    rlayer = QgsRasterLayer(shc_filepath, '')
    colors = list(map(hex_to_rgb, SCORING_COLORS_SHC))
    renderer = get_quantile_renderer(rlayer, colors)
    renderer.setOpacity(0.8)
    rlayer.setRenderer(renderer)
    rlayer.setBlendMode(QPainter.CompositionMode_Multiply)
    rlayer.setContrastEnhancement(QgsContrastEnhancement.StretchToMinimumMaximum,
                                  QgsRasterMinMaxOrigin.MinMax)

    # 等量区分QML -> ラベル置換 -> 桁丸目 -> 出力
    with tempfile.NamedTemporaryFile(delete=False, suffix='.qml') as temp_qml:
        rlayer.saveNamedStyle(temp_qml.name)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.qml') as temp_qml_value_rounded:
            round_label_precision(temp_qml.name,
                                  temp_qml_value_rounded.name,
                                  precision=4)
            output_filepath = replace_colorramp_labels(temp_qml_value_rounded.name,
                                                       os.path.join(
                                                           output_dir, OUTPUT_SHC["FILE_NAME"] + '_score.qml'),
                                                       labels=get_colorramp_label_prefixes("shc"))
    return output_filepath
