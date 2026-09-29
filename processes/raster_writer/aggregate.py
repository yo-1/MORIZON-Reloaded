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

from ...diag_log import log, timed


def generate(
    zoning_layer: QgsRasterLayer, polygon_layer: QgsVectorLayer, output_path: str
):
    # zonalstatistics
    with timed("native:zonalstatisticsfb"):
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
    with timed("native:zonalhistogram"):
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
    # 診断用: ヒストグラムの列構成を確認する（挙動は変更しない）。
    # 入力ラスタがFloat型の場合の警告が実害を生むのは、次のような場合に限られる。
    #   - あるクラスが全ポリゴンに存在しない → count_N 列自体が作られず ratio_N がNULLになる
    #   - 値が整数でない → 想定外の列（例: count_2.5）が作られる
    field_names = [fld.name() for fld in vlayer.fields()]
    count_fields = sorted(n for n in field_names if n.startswith("count_"))
    expected_fields = [f"count_{i}" for i in (1, 2, 3, 4)]
    log(f"ゾーンヒストグラムの出力: features={vlayer.featureCount()}, "
        f"count列={count_fields}")
    missing_fields = [n for n in expected_fields if n not in field_names]
    if missing_fields:
        log(f"count列が不足しています: {missing_fields}。該当クラスが集計範囲に"
            "存在しない場合、対応する ratio_* は NULL になります", Qgis.Warning)
    # count_NODATA は native:zonalhistogram が NoData セル数として常に出力する正規の列。
    # 異常ではないため、想定外の列の判定から除外する（dev4 では誤検知していた）。
    unexpected_fields = [
        n for n in count_fields
        if n not in expected_fields and n != "count_NODATA"
    ]
    if unexpected_fields:
        log(f"想定外のcount列があります: {unexpected_fields}。ゾーニングラスタに"
            "1〜4以外の値が含まれている可能性があります", Qgis.Warning)
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

    with timed(f"ratio列の計算（{vlayer.featureCount()}ポリゴン）"):
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
