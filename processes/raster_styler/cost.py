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

from .utils import (
    get_quantile_renderer,
    hex_to_rgb,
    replace_colorramp_labels,
    get_colorramp_label_prefixes,
    round_label_precision
)
from ..costcsv_parser import CostcsvParser
from ...constants import (
    OUTPUT_COST,
    RAWDATA_COLORS_COST,
    SCORING_COLORS_COST
)


def write_rawdata_qml(costcsv_filepath: str, output_dir: str) -> str:
    csv_parser = CostcsvParser(costcsv_filepath)
    score_names = csv_parser.get_score_names()

    qml_str = f"""
<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis maxScale="0" version="3.16.9-Hannover" styleCategories="AllStyleCategories" hasScaleBasedVisibilityFlag="0" minScale="1e+08">
  <flags>
    <Identifiable>1</Identifiable>
    <Removable>1</Removable>
    <Searchable>1</Searchable>
  </flags>
  <temporal mode="0" fetchMode="0" enabled="0">
    <fixedRange>
      <start></start>
      <end></end>
    </fixedRange>
  </temporal>
  <customproperties>
    <property key="WMSBackgroundLayer" value="false"/>
    <property key="WMSPublishDataSourceUrl" value="false"/>
    <property key="embeddedWidgets/count" value="0"/>
    <property key="identify/format" value="Value"/>
  </customproperties>
  <pipe>
    <provider>
      <resampling zoomedOutResamplingMethod="nearestNeighbour" enabled="false" zoomedInResamplingMethod="nearestNeighbour" maxOversampling="2"/>
    </provider>
    <rasterrenderer alphaBand="-1" band="1" nodataColor="" type="paletted" opacity="0.8">
      <rasterTransparency/>
      <minMaxOrigin>
        <limits>None</limits>
        <extent>WholeRaster</extent>
        <statAccuracy>Estimated</statAccuracy>
        <cumulativeCutLower>0.02</cumulativeCutLower>
        <cumulativeCutUpper>0.98</cumulativeCutUpper>
        <stdDevFactor>2</stdDevFactor>
      </minMaxOrigin>
      <colorPalette>
        <paletteEntry color="{RAWDATA_COLORS_COST[0]}" label="0: {score_names[0]}" value="0" alpha="255"/>
        <paletteEntry color="{RAWDATA_COLORS_COST[1]}" label="1: {score_names[1]}" value="1" alpha="255"/>
        <paletteEntry color="{RAWDATA_COLORS_COST[2]}" label="2: {score_names[2]}" value="2" alpha="255"/>
        <paletteEntry color="{RAWDATA_COLORS_COST[3]}" label="3: {score_names[3]}" value="3" alpha="255"/>
        <paletteEntry color="{RAWDATA_COLORS_COST[4]}" label="4: {score_names[4]}" value="4" alpha="255"/>
        <paletteEntry color="{RAWDATA_COLORS_COST[5]}" label="5: {score_names[5]}" value="5" alpha="255"/>
        <paletteEntry color="{RAWDATA_COLORS_COST[6]}" label="6: {score_names[6]}" value="6" alpha="255"/>
        <paletteEntry color="{RAWDATA_COLORS_COST[7]}" label="7: {score_names[7]}" value="7" alpha="255"/>
        <paletteEntry color="{RAWDATA_COLORS_COST[8]}" label="8: {score_names[8]}" value="8" alpha="255"/>
        <paletteEntry color="{RAWDATA_COLORS_COST[9]}" label="9: {score_names[9]}" value="9" alpha="255"/>
        <paletteEntry color="{RAWDATA_COLORS_COST[10]}" label="10: {score_names[10]}" value="10" alpha="255"/>
      </colorPalette>
      <colorramp type="randomcolors" name="[source]"/>
    </rasterrenderer>
    <brightnesscontrast contrast="0" gamma="1" brightness="0"/>
    <huesaturation grayscaleMode="0" colorizeRed="255" colorizeStrength="100" saturation="0" colorizeGreen="128" colorizeOn="0" colorizeBlue="128"/>
    <rasterresampler maxOversampling="2"/>
    <resamplingStage>resamplingFilter</resamplingStage>
  </pipe>
  <blendMode>6</blendMode>
</qgis>
    """

    output_filepath = os.path.join(
        output_dir, OUTPUT_COST["FILE_NAME"] + '_raw.qml')
    with open(output_filepath, mode='w') as f:
        f.write(qml_str)

    return output_filepath


def write_scoring_qml(cost_filepath: str, output_dir: str) -> str:
    rlayer = QgsRasterLayer(cost_filepath, '')
    colors = list(map(hex_to_rgb, SCORING_COLORS_COST))
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
                                  precision=0)
            output_filepath = replace_colorramp_labels(temp_qml_value_rounded.name,
                                                       os.path.join(
                                                           output_dir, OUTPUT_COST["FILE_NAME"] + '_score.qml'),
                                                       labels=get_colorramp_label_prefixes("cost"))
    return output_filepath
