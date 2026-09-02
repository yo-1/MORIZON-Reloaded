# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

import os

from ...constants import (
    OUTPUT_SAVEAREA,
    RAWDATA_COLORS_SAVEAREA,
    SCORING_COLORS_SAVEAREA
)

from ...settings_manager import SettingsManager


def write_rawdata_qml(output_dir: str) -> str:
    output_filepath = os.path.join(output_dir,
                                   OUTPUT_SAVEAREA["FILE_NAME"] + "_raw.qml")
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
        <paletteEntry color="{RAWDATA_COLORS_SAVEAREA[0]}" label="0" value="0" alpha="255"/>
        <paletteEntry color="{RAWDATA_COLORS_SAVEAREA[1]}" label="1" value="1" alpha="255"/>
      </colorPalette>
      <colorramp type="randomcolors" name="[source]"/>
    </rasterrenderer>
    <brightnesscontrast contrast="0" gamma="1" brightness="0"/>
    <huesaturation grayscaleMode="0" colorizeRed="255" colorizeStrength="100" saturation="0" colorizeGreen="128" colorizeOn="0" colorizeBlue="128"/>
    <rasterresampler maxOversampling="2"/>
    <resamplingStage>resamplingFilter</resamplingStage>
  </pipe>
  <blendMode>6</blendMode>
</qgis>""")
        return output_filepath


def write_scoring_qml(output_dir: str) -> str:
    settings_manager = SettingsManager()
    scores_savearea = settings_manager.get_setting("scores_savearea")

    output_filepath = os.path.join(output_dir,
                                   OUTPUT_SAVEAREA["FILE_NAME"] + "_score.qml")
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
        <paletteEntry color="{SCORING_COLORS_SAVEAREA[0]}" label="{scores_savearea[0]}点（保全対象を含まない流域）" value="0" alpha="255"/>
        <paletteEntry color="{SCORING_COLORS_SAVEAREA[1]}" label="{scores_savearea[1]}点（保全対象を含む流域）" value="1" alpha="255"/>
      </colorPalette>
      <colorramp type="randomcolors" name="[source]"/>
    </rasterrenderer>
    <brightnesscontrast contrast="0" gamma="1" brightness="0"/>
    <huesaturation grayscaleMode="0" colorizeRed="255" colorizeStrength="100" saturation="0" colorizeGreen="128" colorizeOn="0" colorizeBlue="128"/>
    <rasterresampler maxOversampling="2"/>
    <resamplingStage>resamplingFilter</resamplingStage>
  </pipe>
  <blendMode>6</blendMode>
</qgis>""")
        return output_filepath
