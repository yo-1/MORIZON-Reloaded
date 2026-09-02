# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

import tempfile
import xml.etree.ElementTree as ET
import sys

from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.PyQt.QtWidgets import *
from qgis.core import *
from qgis.gui import *

from ...settings_manager import SettingsManager


def get_quantile_renderer(rlayer: QgsRasterLayer, colors=[[255, 255, 255], [255, 0, 0]]):
    """
    QGIS 3.44 対応の等量（Quantile）レンダラーを生成する。

    QGIS 3.16 では classificationMin/Max が暗黙に取得されるケースがあったが、
    QGIS 3.44 では未設定のまま createShader(Quantile) を呼ぶと、分類値が NaN
    になることがある。このため、入力ラスタの実統計値を明示的に設定し、
    Quantile 分類に使用する extent も指定する。
    """
    import math

    if not rlayer.isValid():
        raise RuntimeError(f"ラスターを開けません: {rlayer.source()}")

    provider = rlayer.dataProvider()
    stats = provider.bandStatistics(
        1,
        QgsRasterBandStats.Min | QgsRasterBandStats.Max,
        rlayer.extent(),
        0
    )
    min_value = stats.minimumValue
    max_value = stats.maximumValue

    if not math.isfinite(min_value) or not math.isfinite(max_value):
        raise RuntimeError(
            f"ラスター統計値を取得できません（Min={min_value}, Max={max_value}）: "
            f"{rlayer.source()}"
        )
    if min_value > max_value:
        raise RuntimeError(
            f"ラスター統計値が不正です（Min={min_value}, Max={max_value}）: "
            f"{rlayer.source()}"
        )

    renderer = QgsSingleBandPseudoColorRenderer(provider, 1)
    renderer.setClassificationMin(min_value)
    renderer.setClassificationMax(max_value)

    qcolors = [QColor(*color) for color in colors]
    color_ramp = QgsPresetSchemeColorRamp(qcolors)

    renderer.createShader(
        color_ramp,
        colorRampType=Qgis.ShaderInterpolationMethod.Discrete,
        classificationMode=Qgis.ShaderClassificationMethod.Quantile,
        classes=len(colors),
        clip=False,
        extent=rlayer.extent()
    )

    return renderer



def get_two_class_quantile_threshold_from_file(filepath: str) -> int:
    """QGIS 3.44互換: 2区分表示用Quantile(50%点)をラスターから直接取得。"""
    import numpy as np
    from osgeo import gdal
    gdal.UseExceptions()
    ds = gdal.Open(filepath, gdal.GA_ReadOnly)
    if ds is None:
        raise RuntimeError(f"Quantile計算対象ラスターを開けません: {filepath}")
    band = ds.GetRasterBand(1)
    arr = band.ReadAsArray()
    if arr is None:
        ds = None
        raise RuntimeError(f"Quantile計算対象ラスターを読み込めません: {filepath}")
    arr = np.asarray(arr)
    valid = np.isfinite(arr)
    nodata = band.GetNoDataValue()
    if nodata is not None:
        try:
            if np.isnan(float(nodata)):
                valid &= ~np.isnan(arr)
            else:
                valid &= ~np.isclose(arr, float(nodata), rtol=0.0, atol=1.0e-12)
        except (TypeError, ValueError):
            pass
    values = arr[valid]
    ds = None
    if values.size == 0:
        raise RuntimeError(f"Quantile計算に使用できる有効セルがありません: {filepath}")
    try:
        q50 = np.quantile(values.astype(np.float64, copy=False), 0.5, method="linear")
    except TypeError:
        q50 = np.quantile(values.astype(np.float64, copy=False), 0.5, interpolation="linear")
    if not np.isfinite(q50):
        raise RuntimeError(f"Quantileしきい値が有限値になりません: {filepath}")
    return int(round(float(q50)))


def hex_to_rgb(hex: str) -> str:
    # https://stackoverflow.com/questions/29643352/converting-hex-to-rgb-value-in-python
    h = hex.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def __make_qml_str_with(items_str: str) -> str:
    return f"""
<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis maxScale="0" minScale="1e+08" styleCategories="AllStyleCategories" version="3.16.6-Hannover" hasScaleBasedVisibilityFlag="0">
  <flags>
    <Identifiable>1</Identifiable>
    <Removable>1</Removable>
    <Searchable>1</Searchable>
  </flags>
  <temporal mode="0" enabled="0" fetchMode="0">
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
    <rasterrenderer alphaBand="-1" band="1" nodataColor="" classificationMin="0" opacity="1" type="singlebandpseudocolor" classificationMax="10000">
      <rasterTransparency/>
      <minMaxOrigin>
        <limits>None</limits>
        <extent>WholeRaster</extent>
        <statAccuracy>Estimated</statAccuracy>
        <cumulativeCutLower>0.02</cumulativeCutLower>
        <cumulativeCutUpper>0.98</cumulativeCutUpper>
        <stdDevFactor>2</stdDevFactor>
      </minMaxOrigin>
      <rastershader>
        <colorrampshader maximumValue="10000" minimumValue="0" classificationMode="1" labelPrecision="4" clip="0" colorRampType="DISCRETE">
          <colorramp name="[source]" type="gradient">
            <prop v="247,251,255,255" k="color1"/>
            <prop v="8,48,107,255" k="color2"/>
            <prop v="0" k="discrete"/>
            <prop v="gradient" k="rampType"/>
            <prop v="0.13;222,235,247,255:0.26;198,219,239,255:0.39;158,202,225,255:0.52;107,174,214,255:0.65;66,146,198,255:0.78;33,113,181,255:0.9;8,81,156,255" k="stops"/>
          </colorramp>
          {items_str}
        </colorrampshader>
      </rastershader>
    </rasterrenderer>
    <brightnesscontrast gamma="1" brightness="0" contrast="0"/>
    <huesaturation saturation="0" colorizeOn="0" grayscaleMode="0" colorizeStrength="100" colorizeBlue="128" colorizeRed="255" colorizeGreen="128"/>
    <rasterresampler maxOversampling="2"/>
    <resamplingStage>resamplingFilter</resamplingStage>
  </pipe>
  <blendMode>0</blendMode>
</qgis>
    """


def __write_qmlfile(qml_str: str, output_filepath=None):
    """
    文字列をQMLファイルに書き出す
    出力先が明示されていない場合は一時ファイルに書き出す
    Returns:
        str: 生成されたQMLのファイルパス
    """
    if output_filepath is None:
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(qml_str)
            return f.name
    else:
        with open(output_filepath, mode='w') as f:
            f.write(qml_str)
            return output_filepath


def write_qml_deviding_by_threshold(threshold: int,
                                    lower_color: str,
                                    higher_color: str,
                                    output_filepath=None) -> str:
    """しきい値1つで2つに区分したラスタースタイルを書き出す
    しきい値が1の場合、ラベルは低(>= 1), 高(> 1)となる

    Args:
        threshold: しきい値
        lower_color: しきい値以下の区分の色
        higher_color: しきい値より大きい区分の色
        output_filepath: QMLの出力先ファイルパス、任意
    Returns:
        str: 生成されたQMLのファイルパス
    """
    # 通常、色分けのしきい値の境界値は、境界より小さいほうの区分に含まれる
    # 例：しきい値=6 => 区分1:6以下, 区分2:6よりも大きい値
    # しかしQGIS3.16では、2区分の場合のみ境界より大きいほうの区分に含まれてしまう
    # 例：しきい値=6 => 区分1:6よりも小さい値, 区分2:6以上
    # GUIの表記とも異なるので明らかに不具合だが、プラグインで修正することは難しい
    # 今回は整数値同士の比較なので、0に近い非常に小さい値を加算することでこの問題を迂回する
    offset_threshold = threshold + 0.0000001

    items_str = f"""
        <item value="{offset_threshold}" color="{lower_color}" label="低(&lt;= {threshold})" alpha="255"/>
        <item value="inf" color="{higher_color}" label="高(> {threshold})" alpha="255"/>
    """

    qml_str = __make_qml_str_with(items_str)
    return __write_qmlfile(qml_str, output_filepath)


def write_qml_by_thresholds_and_colors(thresholds: tuple,
                                       colors: tuple,
                                       scores: tuple,
                                       output_filepath=None) -> str:
    """しきい値で区分して色分けしたラスタースタイルを書き出す
    ラベル例：1点(>= 1), 2点(1 -2), 3点(> 2)

    Args:
        thresholds: しきい値
        colors: 区分ごとの色、len(colors) == len(threshold) + 1
        scores: 区分ごとのスコア、len(colors) == len(scores)
        output_filepath: QMLの出力先ファイルパス、任意

    Returns:
        str: 生成されたQMLのファイルパス
    """
    items_str = ""
    for i in range(len(colors)):
        if i == 0:
            items_str += f'<item value="{thresholds[i]}" color="{colors[i]}" label="{scores[i]}点(&lt;= {thresholds[i]})" alpha="255"/>'
        elif i == len(colors) - 1:
            items_str += f'<item value="inf" color="{colors[i]}" label="{scores[i]}点(> {thresholds[i-1]})" alpha="255"/>'
        else:
            items_str += f'<item value="{thresholds[i]}" color="{colors[i]}" label="{scores[i]}点({thresholds[i-1]} - {thresholds[i]})" alpha="255"/>'

    qml_str = __make_qml_str_with(items_str)
    return __write_qmlfile(qml_str, output_filepath)


def _get_colorramp_items_from_qml_root(root):
    """
    QGIS 3.16/3.44 のQML構造差を吸収して colorrampshader/item を取得する。
    3.44では保存条件により中間ノード構造が変わることがあるため、
    固定パス root.find('pipe/...') に依存しない。
    """
    shader = root.find(".//colorrampshader")
    if shader is None:
        return []
    return list(shader.findall("item"))


def replace_colorramp_labels(qml_filepath: str, output_filepath: str, labels=[]) -> str:
    """
    QMLをパースして区分ごとの凡例ラベル文字列を所定の規則に置き換え、新たなQMLを生成する
    所定のルール：1点(<= 1), 2点(1 - 2), 3点(> 2)

    Args:
        qml_filepath (str)
        output_filepath (str)
        labels (list, optional): 設定したいラベル文字列の配列. Defaults to [].

    Raises:
        Exception: labelsが、QMLで定義されている色の数よりも少ない場合

    Returns:
        str: 生成されたQMLのファイルパス
    """
    tree = ET.parse(qml_filepath)
    root = tree.getroot()
    items = _get_colorramp_items_from_qml_root(root)
    if not items:
        raise RuntimeError(
            "QML内に連続値カラ―ランプ（colorrampshader/item）が見つかりません。"
            "QGIS 3.44のQML構造またはレイヤ描画方式が旧版と異なります。"
        )

    if len(items) > len(labels):
        raise Exception("labelsの配列長は、QMLで定義されている色の数以上でなければなりません")

    for i in range(len(items)):
        if i == 0:
            new_label = f"{labels[i]}(<= {items[i].attrib['value']})"
        elif i == len(items) - 1:
            new_label = f"{labels[i]}(> {items[i-1].attrib['value']})"
        else:
            new_label = f"{labels[i]}({items[i-1].attrib['value']} - {items[i].attrib['value']})"

        # ラベル定義を上書き
        items[i].attrib["label"] = new_label

    tree.write(output_filepath)
    return output_filepath


def get_colorramp_label_prefixes(raster_name: str) -> list:
    """
    スタイルの区分ごとの凡例ラベルに表示する接頭辞を取得する
    接頭辞にはその区分のスコアが入る（1点とか2点とか）
    スコアはQGISの設定値から読み出す
    """
    settings_manager = SettingsManager()
    scores_siteidx = settings_manager.get_setting(f"scores_{raster_name}")
    return list(map(lambda score: str(score) + "点", scores_siteidx))


def round_label_precision(qml_filepath: str, output_filepath: str, precision=2) -> str:
    """
    QMLをパースして、等量区分のしきい値の小数点精度を丸めて、別ファイルに書き出す

    Args:
        qml_filepath (str)
        output_filepath (str)

    Returns:
        str: 出力ファイルパス
    """
    tree = ET.parse(qml_filepath)
    root = tree.getroot()
    items = _get_colorramp_items_from_qml_root(root)
    if not items:
        raise RuntimeError(
            "QML内に連続値カラ―ランプ（colorrampshader/item）が見つかりません。"
            "QGIS 3.44のQML構造またはレイヤ描画方式が旧版と異なります。"
        )
    # 小数点精度がゼロなら整数値に丸める

    def round_method(val):
        return round(val, precision) if precision > 0 else round(val)

    for item in items:
        item.attrib['value'] = str(round_method(
            float(item.attrib['value']))) if item.attrib['value'] != 'inf' else 'inf'

    tree.write(output_filepath)
    return output_filepath


def add_tiny_value_to_thresholds(qml_filepath: str, output_filepath: str, tiny_value=0.0000001) -> str:
    """
    QMLをパースして、等量区分のしきい値に0に近い非常に小さい値を加算して、別ファイルに書き出す

    この関数の使い道は以下のとおり
    通常、色分けのしきい値の境界値は、境界より小さいほうの区分に含まれる
    例：しきい値=6 => 区分1:6以下, 区分2:6よりも大きい値
    しかしQGIS3.16では、2区分の場合のみ境界より大きいほうの区分に含まれてしまう
    例：しきい値=6 => 区分1:6よりも小さい値, 区分2:6以上
    GUIの表記とも異なるので明らかに不具合だが、プラグインで修正することは難しい
    今回は整数値同士の比較なので、0に近い非常に小さい値を加算することでこの問題を迂回する

    Args:
        qml_filepath (str)
        output_filepath (str)
        tiny_value (float) default to 0.0000001

    Returns:
        str: 出力ファイルパス
    """
    tree = ET.parse(qml_filepath)
    root = tree.getroot()
    items = _get_colorramp_items_from_qml_root(root)
    if not items:
        raise RuntimeError(
            "QML内に連続値カラ―ランプ（colorrampshader/item）が見つかりません。"
            "QGIS 3.44のQML構造またはレイヤ描画方式が旧版と異なります。"
        )

    # しきい値に小さい値を加算
    for item in items:
        item.attrib['value'] = str(float(
            item.attrib['value']) + tiny_value) if item.attrib['value'] != 'inf' else 'inf'

    tree.write(output_filepath)
    return output_filepath
