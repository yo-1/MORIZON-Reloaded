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
    OUTPUT_DISTANCE,
    SCORING_COLORS_DISTANCE,
    RAWDATA_COLORS_DISTANCE
)
from .utils import (
    get_quantile_renderer,
    hex_to_rgb,
    replace_colorramp_labels,
    get_colorramp_label_prefixes,
    round_label_precision
)


def write_rawdata_qml(output_dir: str) -> str:
    output_filepath = os.path.join(output_dir,
                                   OUTPUT_DISTANCE["FILE_NAME"] + "_raw.qml")
    with open(output_filepath, mode="w") as f:
        f.write(f"""
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
    <rasterrenderer alphaBand="-1" classificationMin="0" band="1" nodataColor="" type="singlebandpseudocolor" opacity="0.8" classificationMax="6738.58325557328">
      <rasterTransparency/>
      <minMaxOrigin>
        <limits>MinMax</limits>
        <extent>WholeRaster</extent>
        <statAccuracy>Estimated</statAccuracy>
        <cumulativeCutLower>0.02</cumulativeCutLower>
        <cumulativeCutUpper>0.98</cumulativeCutUpper>
        <stdDevFactor>2</stdDevFactor>
      </minMaxOrigin>
      <rastershader>
        <colorrampshader labelPrecision="4" colorRampType="DISCRETE" classificationMode="3" maximumValue="6738.58325557328" minimumValue="0" clip="0">
          <colorramp type="gradient" name="[source]">
            <prop k="color1" v="247,251,255,255"/>
            <prop k="color2" v="8,48,107,255"/>
            <prop k="discrete" v="0"/>
            <prop k="rampType" v="gradient"/>
            <prop k="stops" v="0.13;222,235,247,255:0.26;198,219,239,255:0.39;158,202,225,255:0.52;107,174,214,255:0.65;66,146,198,255:0.78;33,113,181,255:0.9;8,81,156,255"/>
          </colorramp>
          <item color="{RAWDATA_COLORS_DISTANCE[0]}" label="&lt;= 200" value="200" alpha="255"/>
          <item color="{RAWDATA_COLORS_DISTANCE[1]}" label="200 - 400" value="400" alpha="255"/>
          <item color="{RAWDATA_COLORS_DISTANCE[2]}" label="400 - 600" value="600" alpha="255"/>
          <item color="{RAWDATA_COLORS_DISTANCE[3]}" label="600 - 800" value="800" alpha="255"/>
          <item color="{RAWDATA_COLORS_DISTANCE[4]}" label="800 - 1000" value="1000" alpha="255"/>
          <item color="{RAWDATA_COLORS_DISTANCE[5]}" label="> 1000" value="inf" alpha="255"/>
        </colorrampshader>
      </rastershader>
    </rasterrenderer>
    <brightnesscontrast contrast="0" gamma="1" brightness="0"/>
    <huesaturation grayscaleMode="0" colorizeRed="255" colorizeStrength="100" saturation="0" colorizeGreen="128" colorizeOn="0" colorizeBlue="128"/>
    <rasterresampler maxOversampling="2"/>
    <resamplingStage>resamplingFilter</resamplingStage>
  </pipe>
  <blendMode>6</blendMode>
</qgis>""")
        return output_filepath


def write_scoring_qml(distance_filepath: str, output_dir: str) -> str:
    rlayer = QgsRasterLayer(distance_filepath, '')
    colors = list(map(hex_to_rgb, SCORING_COLORS_DISTANCE))
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
                                                           output_dir, OUTPUT_DISTANCE["FILE_NAME"] + '_score.qml'),
                                                       labels=get_colorramp_label_prefixes("distance"))
    return output_filepath
