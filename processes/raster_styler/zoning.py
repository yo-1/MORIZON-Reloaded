# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

import os

from ...constants import (
    OUTPUT_ZONING,
    ZONING_COLORS
)


def write_qml(output_dir: str) -> str:
    output_filepath = os.path.join(output_dir,
                                   OUTPUT_ZONING["FILE_NAME"] + ".qml")
    with open(output_filepath, mode="w") as f:
        f.write(f"""
    <!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis hasScaleBasedVisibilityFlag="0" minScale="1e+08" version="3.16.7-Hannover" maxScale="0" styleCategories="AllStyleCategories">
  <flags>
    <Identifiable>1</Identifiable>
    <Removable>1</Removable>
    <Searchable>1</Searchable>
  </flags>
  <temporal fetchMode="0" enabled="0" mode="0">
    <fixedRange>
      <start></start>
      <end></end>
    </fixedRange>
  </temporal>
  <customproperties>
    <property value="false" key="WMSBackgroundLayer"/>
    <property value="false" key="WMSPublishDataSourceUrl"/>
    <property value="0" key="embeddedWidgets/count"/>
    <property value="Value" key="identify/format"/>
  </customproperties>
  <pipe>
    <provider>
      <resampling zoomedInResamplingMethod="nearestNeighbour" maxOversampling="2" enabled="false" zoomedOutResamplingMethod="nearestNeighbour"/>
    </provider>
    <rasterrenderer band="1" type="paletted" nodataColor="" alphaBand="-1" opacity="1">
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
        <paletteEntry color="{ZONING_COLORS[0]}" value="1" label="第1象限（災害リスクに注意）" alpha="255"/>
        <paletteEntry color="{ZONING_COLORS[1]}" value="2" label="第2象限（林業経営適地）" alpha="255"/>
        <paletteEntry color="{ZONING_COLORS[2]}" value="3" label="第3象限（要収益性向上）" alpha="255"/>
        <paletteEntry color="{ZONING_COLORS[3]}" value="4" label="第4象限（災害に強い森林管理）" alpha="255"/>
      </colorPalette>
      <colorramp type="preset" name="[source]">
        <prop v="255,187,128,255" k="preset_color_0"/>
        <prop v="153,239,128,255" k="preset_color_1"/>
        <prop v="26,219,255,255" k="preset_color_2"/>
        <prop v="128,167,255,255" k="preset_color_3"/>
        <prop v="#ff7780" k="preset_color_name_0"/>
        <prop v="#33df80" k="preset_color_name_1"/>
        <prop v="#1aceff" k="preset_color_name_2"/>
        <prop v="#806eff" k="preset_color_name_3"/>
        <prop v="preset" k="rampType"/>
      </colorramp>
    </rasterrenderer>
    <brightnesscontrast contrast="0" gamma="1" brightness="0"/>
    <huesaturation colorizeOn="0" colorizeStrength="100" colorizeBlue="128" colorizeGreen="128" saturation="0" colorizeRed="255" grayscaleMode="0"/>
    <rasterresampler maxOversampling="2"/>
    <resamplingStage>resamplingFilter</resamplingStage>
  </pipe>
  <blendMode>0</blendMode>
</qgis>
    """)

    return output_filepath
