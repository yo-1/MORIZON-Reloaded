# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import *
import processing


def generate(
    zoning_layer: QgsRasterLayer, polygon_layer: QgsVectorLayer, output_path: str
):
    # zonalstatistics
    stat_layer = processing.run(
        "native:zonalstatisticsfb",
        {
            "COLUMN_PREFIX": "_",
            "INPUT": polygon_layer,
            "INPUT_RASTER": zoning_layer,
            "OUTPUT": "TEMPORARY_OUTPUT",
            "RASTER_BAND": 1,
            "STATISTICS": [0, 2, 5, 6, 9],
        },
    )[
        "OUTPUT"
    ]  # ピクセル数・平均・最大・最小・最頻

    # zonalhistogram(1,2,3,4それぞれの出現頻度)
    processing.run(
        "native:zonalhistogram",
        {
            "INPUT_RASTER": zoning_layer,
            "INPUT_VECTOR": stat_layer,
            "OUTPUT": output_path,
            "RASTER_BAND": 1,
            "COLUMN_PREFIX": "count_",
        },
    )

    # 1,2,3,4それぞれが占める割合
    vlayer = QgsVectorLayer(output_path, "org")
    vlayer.dataProvider().addAttributes(
        [
            QgsField(name="ratio_1", type=QVariant.Double, len=6, prec=3),
            QgsField(name="ratio_2", type=QVariant.Double, len=6, prec=3),
            QgsField(name="ratio_3", type=QVariant.Double, len=6, prec=3),
            QgsField(name="ratio_4", type=QVariant.Double, len=6, prec=3),
            QgsField(name="count_1_4", type=QVariant.Double, len=6, prec=3),
            QgsField(name="ratio_1_4", type=QVariant.Double, len=6, prec=3),
        ]
    )
    vlayer.updateFields()

    exp_ratio_1 = QgsExpression('"count_1"/"_count"')
    exp_ratio_2 = QgsExpression('"count_2"/"_count"')
    exp_ratio_3 = QgsExpression('"count_3"/"_count"')
    exp_ratio_4 = QgsExpression('"count_4"/"_count"')
    exp_cnt_1_4 = QgsExpression('"count_1"+"count_4"')
    exp_ratio_1_4 = QgsExpression('("count_1"+"count_4")/"_count"')

    context = QgsExpressionContext()
    context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(vlayer))

    with edit(vlayer):
        for f in vlayer.getFeatures():
            context.setFeature(f)
            f["ratio_1"] = exp_ratio_1.evaluate(context)
            f["ratio_2"] = exp_ratio_2.evaluate(context)
            f["ratio_3"] = exp_ratio_3.evaluate(context)
            f["ratio_4"] = exp_ratio_4.evaluate(context)
            f["count_1_4"] = exp_cnt_1_4.evaluate(context)
            f["ratio_1_4"] = exp_ratio_1_4.evaluate(context)

            vlayer.updateFeature(f)

    return output_path
