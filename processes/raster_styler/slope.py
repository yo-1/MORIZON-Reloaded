# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

import os

from ...constants import (
    OUTPUT_SLOPE,
    RAWDATA_COLORS_SLOPE,
    SCORING_COLORS_SLOPE
)

from ...settings_manager import SettingsManager


def write_rawdata_qml(output_dir: str) -> str:
    output_filepath = os.path.join(output_dir,
                                   OUTPUT_SLOPE["FILE_NAME"] + "_raw.qml")
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
    <rasterrenderer alphaBand="-1" classificationMin="0" band="1" nodataColor="" type="singlebandpseudocolor" opacity="0.8" classificationMax="73.9964905">
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
        <colorrampshader labelPrecision="4" colorRampType="DISCRETE" classificationMode="1" maximumValue="73.99649049999999" minimumValue="0" clip="0">
          <colorramp type="gradient" name="[source]">
            <prop k="color1" v="247,252,245,255"/>
            <prop k="color2" v="0,68,27,255"/>
            <prop k="discrete" v="0"/>
            <prop k="rampType" v="gradient"/>
            <prop k="stops" v="0.13;229,245,224,255:0.26;199,233,192,255:0.39;161,217,155,255:0.52;116,196,118,255:0.65;65,171,93,255:0.78;35,139,69,255:0.9;0,109,44,255"/>
          </colorramp>
          <item color="{RAWDATA_COLORS_SLOPE[0]}" label="&lt;= 20" value="20" alpha="255"/>
          <item color="{RAWDATA_COLORS_SLOPE[1]}" label="20 - 25" value="25" alpha="255"/>
          <item color="{RAWDATA_COLORS_SLOPE[2]}" label="25 - 30" value="30" alpha="255"/>
          <item color="{RAWDATA_COLORS_SLOPE[3]}" label="30 - 35" value="35" alpha="255"/>
          <item color="{RAWDATA_COLORS_SLOPE[4]}" label="35 - 40" value="40" alpha="255"/>
          <item color="{RAWDATA_COLORS_SLOPE[5]}" label="40 - 45" value="45" alpha="255"/>
          <item color="{RAWDATA_COLORS_SLOPE[6]}" label="> 45" value="inf" alpha="255"/>
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


def write_scoring_qml(output_dir: str) -> str:
    settings_manager = SettingsManager()
    scores_slope = settings_manager.get_setting("scores_slope")
    output_filepath = os.path.join(output_dir,
                                   OUTPUT_SLOPE["FILE_NAME"] + "_score.qml")
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
    <rasterrenderer alphaBand="-1" classificationMin="0" band="1" nodataColor="" type="singlebandpseudocolor" opacity="0.8" classificationMax="73.9964905">
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
        <colorrampshader labelPrecision="4" colorRampType="DISCRETE" classificationMode="1" maximumValue="73.99649049999999" minimumValue="0" clip="0">
          <colorramp type="gradient" name="[source]">
            <prop k="color1" v="0,0,4,255"/>
            <prop k="color2" v="252,253,191,255"/>
            <prop k="discrete" v="0"/>
            <prop k="rampType" v="gradient"/>
            <prop k="stops" v="0.0196078;2,2,11,255:0.0392157;5,4,22,255:0.0588235;9,7,32,255:0.0784314;14,11,43,255:0.0980392;20,14,54,255:0.117647;26,16,66,255:0.137255;33,17,78,255:0.156863;41,17,90,255:0.176471;49,17,101,255:0.196078;57,15,110,255:0.215686;66,15,117,255:0.235294;74,16,121,255:0.254902;82,19,124,255:0.27451;90,22,126,255:0.294118;98,25,128,255:0.313725;106,28,129,255:0.333333;114,31,129,255:0.352941;121,34,130,255:0.372549;129,37,129,255:0.392157;137,40,129,255:0.411765;145,43,129,255:0.431373;153,45,128,255:0.45098;161,48,126,255:0.470588;170,51,125,255:0.490196;178,53,123,255:0.509804;186,56,120,255:0.529412;194,59,117,255:0.54902;202,62,114,255:0.568627;210,66,111,255:0.588235;217,70,107,255:0.607843;224,76,103,255:0.627451;231,82,99,255:0.647059;236,88,96,255:0.666667;241,96,93,255:0.686275;244,105,92,255:0.705882;247,114,92,255:0.72549;249,123,93,255:0.745098;251,133,96,255:0.764706;252,142,100,255:0.784314;253,152,105,255:0.803922;254,161,110,255:0.823529;254,170,116,255:0.843137;254,180,123,255:0.862745;254,189,130,255:0.882353;254,198,138,255:0.901961;254,207,146,255:0.921569;254,216,154,255:0.941176;253,226,163,255:0.960784;253,235,172,255:0.980392;252,244,182,255"/>
          </colorramp>
          <item color="{SCORING_COLORS_SLOPE[0]}" label="{scores_slope[0]}点(&lt;= 35)" value="35" alpha="255"/>
          <item color="{SCORING_COLORS_SLOPE[1]}" label="{scores_slope[1]}点(35 - 45)" value="45" alpha="255"/>
          <item color="{SCORING_COLORS_SLOPE[2]}" label="{scores_slope[2]}点(> 45)" value="inf" alpha="255"/>
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
