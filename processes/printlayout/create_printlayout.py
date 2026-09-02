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
from qgis.PyQt.QtXml import QDomDocument
from qgis.utils import iface
import os


def generate(target_name, background_layer, target_layer):
    # レイアウトファイルの読み込み
    project = QgsProject.instance()
    composition = QgsPrintLayout(project)
    document = QDomDocument()
    plugin_dir = os.path.dirname(__file__)

    if target_name == "zoning":
        template_file = os.path.join(plugin_dir, "template/zoning_template.qpt")
    else:
        template_file = os.path.join(plugin_dir, "template/aggregate_template.qpt")
    with open(template_file) as f:
        template_content = f.read()

    document.setContent(template_content)
    composition.loadFromTemplate(document, QgsReadWriteContext())
    template_name = composition.name()
    manager = project.layoutManager()
    project.layoutManager().addLayout(composition)
    layout = manager.layoutByName(template_name)

    map = QgsLayoutItemMap(layout)
    map.setRect(QRectF(10, 10, 10, 10))
    map.setLayers([target_layer, background_layer])
    map.setFrameEnabled(True)

    # マップの表示の調整
    map.attemptMove(QgsLayoutPoint(20, 10, QgsUnitTypes.LayoutMillimeters))
    map.attemptResize(QgsLayoutSize(310, 270, QgsUnitTypes.LayoutMillimeters))
    target_layer_extent = get_target_layer_extent(target_layer)
    map.zoomToExtent(target_layer_extent)
    layout.addLayoutItem(map)

    # 方位記号アイテムの方向を地図の回転と同期
    azimuth_icon = layout.itemById("方位記号")
    azimuth_icon.setLinkedMap(map)

    # スケールバーの追加
    scalebar = QgsLayoutItemScaleBar(layout)
    scalebar.setFont(QFont("Arial", 14))
    scalebar.setStyle("Single Box")
    scalebar.setFillColor(QColor("Black"))
    scalebar.setUnits(QgsUnitTypes.DistanceKilometers)
    scalebar.setUnitLabel("km")
    scalebar.setLinkedMap(map)
    # QGIS 3.40以降は整数ではなくQgisのstrong enumを要求する。
    scalebar.setSegmentSizeMode(Qgis.ScaleBarSegmentSizeMode.FitWidth)
    scalebar.setNumberOfSegmentsLeft(0)
    scalebar.setNumberOfSegments(2)
    scalebar.setMinimumBarWidth(15)
    scalebar.setMaximumBarWidth(120)
    scalebar.update()
    scalebar.setReferencePoint(QgsLayoutItem.Middle)
    layout.addLayoutItem(scalebar)
    scalebar.attemptMove(QgsLayoutPoint(210, 287, QgsUnitTypes.LayoutMillimeters))

    # 凡例の追加
    legend = QgsLayoutItemLegend(layout)
    legend.setAutoUpdateModel(False)
    group = legend.model().rootGroup()
    group.clear()
    group.addLayer(
        QgsProject.instance().layerTreeRoot().findLayer(target_layer.id()).layer()
    )
    layout.addItem(legend)
    legend.attemptMove(QgsLayoutPoint(334, 14, QgsUnitTypes.LayoutMillimeters))
    layout.addLayoutItem(legend)

    # レイアウトを開く
    iface.openLayoutDesigner(layout=layout)


def get_target_layer_extent(target_layer):
    """
    対象のレイヤーのextentをプロジェクトCRSに再投影してから返す
    Returns:
        QgsRectangle
    """
    target_layer_crs = target_layer.crs()
    project_crs = QgsProject.instance().crs()
    transform = QgsCoordinateTransform(
        target_layer_crs, project_crs, QgsProject.instance()
    )
    extent = target_layer.extent()

    leftbottom = QgsPointXY(extent.xMinimum(), extent.yMinimum())
    righttop = QgsPointXY(extent.xMaximum(), extent.yMaximum())
    leftbottom_geom = QgsGeometry.fromPointXY(leftbottom)
    righttop_geom = QgsGeometry.fromPointXY(righttop)
    leftbottom_geom.transform(transform)
    righttop_geom.transform(transform)
    target_layer_extent = QgsRectangle(
        leftbottom_geom.asPoint(), righttop_geom.asPoint()
    )
    return target_layer_extent
