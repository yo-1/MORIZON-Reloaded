# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

import json

# nosec B405 - only parses QGIS's own in-process layer metadata, never
# external/network XML
import xml.etree.ElementTree as ET  # nosec B405 - local XML
import os
import re

from qgis.core import QgsCoordinateReferenceSystem, QgsRasterLayer
import processing

from ..processes import raster_styler
from ..diag_log import timed, count_event
from ..constants import PIXELS_THRESHOLD_RESAMPLING

# O-21対応: get_initial_thresholds()の結果（レイヤーID・分類数単位）をキャッシュする。
# 要素計算完了直後のレイヤー一括追加時、複数のUIコンボボックスが一時的に同一レイヤーを
# 指すことがあり、dev8のScoringObject単位の重複排除（同一コンボボックスの連続呼び出し
# のみ対象）をすり抜けて、全画素走査を伴うこの関数が短時間に何度も呼ばれていた
# （実機ログで7回連続を確認、docs/OPEN_ISSUES.md O-21）。レイヤーの内容が変わる場合は
# QGIS側で新しいレイヤーID（別オブジェクト）になるため、ID単位のキャッシュは安全。
_initial_thresholds_cache = {}


def get_raster_stats(rlayer: QgsRasterLayer) -> dict:
    """ラスターレイヤーの統計値を取得する

    Args:
        rlayer (QgsRasterLayer)

    Returns:
        dict: {'MAX': float, 'MEAN': float, 'MIN': float, 'STD_DEV': float}
    """

    """
    まずはラスターレイヤーのメタデータを読みに行く
    QgsRasterLayerの初期化時に、メタデータには以下のような文字列が書き込まれる
    STATISTICS_MAXIMUM=255
    STATISTICS_MEAN=206.68737191625
    STATISTICS_MINIMUM=0
    STATISTICS_STDDEV=55.286417545366
    これらはHTMLに埋め込まれているのでパースして取り出す
    """

    metadata_stats = {
        "STATISTICS_MAXIMUM": None,
        "STATISTICS_MINIMUM": None,
        "STATISTICS_MEAN": None,
        "STATISTICS_STDDEV": None,
    }

    try:
        # htmlMetadata()はQGIS自身が現在開いているラスターレイヤーについて生成する
        # 内部メタデータ文字列であり、外部・ネットワーク由来のXMLではないため、
        # XXE等の脅威モデルは当てはまらない（banditのB314/B405は汎用ルールとして
        # 誤検知する）。defusedxml追加は、このためだけに新規の外部依存を増やす
        # ことになるため見送る。
        root = ET.fromstring(  # nosec B314
            "<root>"
            + rlayer.dataProvider().htmlMetadata().replace("\n", "")
            + "</root>"
        )
    except ET.ParseError:
        # xyzタイルはhtmlMetadataが適切なXMLとしてパース出来ないので例外をキャッチ
        print(f"failed to parse htmlMetada of {rlayer.name()}, skipping...")
        root = ET.fromstring("<root></root>")  # nosec B314 - literal XML

    for item in root.iter():
        if item.text == "MBTiles":  # GDAL-DriverがMBTilesの場合
            # MBTilesは処理対象外＋計算コストが非常に大きいので、計算せず不正な値を返す（ラスタータイルと同じ値）
            return {
                "MIN": 1000000,
                "MAX": -10000,
                "MEAN": 1000000,
                "STD_DEV": 1,
            }

        if item.text is None:
            continue

        if "=" not in item.text:
            continue

        prefix, value = item.text.split("=")
        if prefix in metadata_stats.keys() and metadata_stats[prefix] is None:
            metadata_stats[prefix] = float(value)

    # メタデータに統計値が含まれていない場合は計算する
    # 診断用: この計算(bandStatistics)は全ピクセルを走査し、UIスレッドから呼ばれる。
    # 遅かった場合だけ記録する（UIイベントから頻繁に呼ばれるため）。処理内容は変更しない。
    with timed(f"ラスター統計の取得 layer={rlayer.name()}", min_seconds=0.3):
        stats = {
            "MAX": (
                metadata_stats["STATISTICS_MAXIMUM"]
                if metadata_stats["STATISTICS_MAXIMUM"] is not None
                else rlayer.dataProvider().bandStatistics(1).maximumValue
            ),
            "MIN": (
                metadata_stats["STATISTICS_MINIMUM"]
                if metadata_stats["STATISTICS_MINIMUM"] is not None
                else rlayer.dataProvider().bandStatistics(1).minimumValue
            ),
            "MEAN": (
                metadata_stats["STATISTICS_MEAN"]
                if metadata_stats["STATISTICS_MEAN"] is not None
                else rlayer.dataProvider().bandStatistics(1).mean
            ),
            "STD_DEV": (
                metadata_stats["STATISTICS_STDDEV"]
                if metadata_stats["STATISTICS_STDDEV"] is not None
                else rlayer.dataProvider().bandStatistics(1).stdDev
            ),
        }

    return stats


def get_initial_thresholds(rlayer: QgsRasterLayer, classes_count=3) -> list:
    """
    ラスタレイヤに対してQGIS Quantile分類の初期閾値を返す。

    QGIS 3.16版は一旦QMLへ保存してXMLから閾値を取り出していたが、
    QGIS 3.44ではsaveNamedStyle()のQML構造が描画方式等により変わり、
    colorrampshaderが存在しない場合がある。

    そこでQGIS 3.44版では、既に生成している
    QgsSingleBandPseudoColorRenderer -> QgsColorRampShader の
    colorRampItemList()から直接分類値を取得する。
    分類方式そのもの（Quantile）は変更しない。
    """
    if classes_count < 2:
        raise Exception("classes_count must be 2 or larger.")
    if rlayer is None or not rlayer.isValid():
        return [0.0 for _ in range(classes_count - 1)]

    cache_key = (rlayer.id(), classes_count)
    if cache_key in _initial_thresholds_cache:
        count_event(f"しきい値初期値のキャッシュ再利用: {rlayer.name()}")
        return _initial_thresholds_cache[cache_key]

    # 画面上のレイヤスタイルを変更しないため、元ファイルから別インスタンスを作る。
    rlayer_filepath = rlayer.dataProvider().dataSourceUri().split("|", 1)[0]
    rlayer_from_path = QgsRasterLayer(rlayer_filepath)
    if not rlayer_from_path.isValid():
        return [0.0 for _ in range(classes_count - 1)]

    # 診断用: UIスレッド上で全ピクセルの統計を取るため、大きなラスターでは
    # ここでQGISが応答しなくなる可能性がある。開始/完了の時刻を残して確認する。
    with timed(f"しきい値初期値の算出（Quantile分類） layer={rlayer.name()}"):
        renderer = raster_styler.get_quantile_renderer(
            rlayer_from_path, [[0, 0, 0] for _ in range(classes_count)]
        )

    try:
        shader = renderer.shader()
        shader_func = (
            shader.rasterShaderFunction() if shader is not None else None
        )
        items = (
            shader_func.colorRampItemList() if shader_func is not None else []
        )
    except Exception:
        items = []

    thresholds = []
    for i in range(classes_count - 1):
        try:
            thresholds.append(round(float(items[i].value), 4))
        except (IndexError, TypeError, ValueError, AttributeError):
            thresholds.append(0.0)

    _initial_thresholds_cache[cache_key] = thresholds
    return thresholds


def find(items: list, x) -> int:
    """
    https://note.nkmk.me/python-list-index/
    配列から要素を検索し、存在すればそのインデックスを返す
    存在しなければ-1を返す

    Args:
        items ([type]): 検索対象の配列
        x ([type]): 検索する値

    Returns:
        int: 見つかった最初の要素のインデックス
    """
    return items.index(x) if x in items else -1


def get_tiff_info(tiff_filepath: str) -> dict:
    """
    DEMの各種情報をgdalinfoを用いて取得する

    Args:
        dem_filepath (str): [description]

    Returns:
        dict: {"crs", "resolution", "extent", "nodata_value", "size"}
    """
    gdalinfo_html = processing.run(
        "gdal:gdalinfo",
        {
            "EXTRA": "-json",
            "INPUT": tiff_filepath,
            "OUTPUT": "TEMPORARY_OUTPUT",
        },
    )["OUTPUT"]

    with open(gdalinfo_html) as f:
        gdalinfo_json = "".join(f.readlines())[5:-6]
        gdalinfo = json.loads(gdalinfo_json)

    crs = QgsCoordinateReferenceSystem.fromWkt(
        gdalinfo["coordinateSystem"]["wkt"]
    )

    extent = [
        gdalinfo["cornerCoordinates"]["upperLeft"][0],
        gdalinfo["cornerCoordinates"]["lowerRight"][0],
        gdalinfo["cornerCoordinates"]["lowerRight"][1],
        gdalinfo["cornerCoordinates"]["upperLeft"][1],
    ]

    return {
        "crs": crs,
        "resolution": gdalinfo["geoTransform"][1],
        "extent": extent,
        "nodata_value": gdalinfo["bands"][0].get("noDataValue"),
        "size": gdalinfo["size"],
    }


def is_valid_elements_layer(rlayer: QgsRasterLayer) -> bool:
    """
    ラスターレイヤーが有効な要素レイヤーかチェックする
    """
    stats = get_raster_stats(rlayer)
    return stats["MIN"] <= stats["MEAN"] and stats["MEAN"] <= stats["MAX"]


def is_valid_scoring_layer(rlayer: QgsRasterLayer) -> bool:
    """
    ラスターレイヤーが有効なスコアリングレイヤーかチェックする
    """
    stats = get_raster_stats(rlayer)
    is_tile = stats["MIN"] >= stats["MAX"]
    has_negative = stats["MIN"] < 0
    not_integer = stats["MIN"] != int(stats["MIN"]) or stats["MAX"] != int(
        stats["MAX"]
    )

    is_invalid = is_tile or has_negative or not_integer
    return not is_invalid


def is_tmpdir_valid():
    """
    システムtempディレクトリーに全角文字がある場合はSAGA/GRASSエラーになるので、不正だと判断する
    """
    return (
        re.search("[^\x01-\x7e]", os.environ["TMP"]) is None
        and re.search("[^\x01-\x7e]", os.environ["TEMP"]) is None
    )


def is_resampling_needed(dem_info: dict) -> bool:
    """
    リサンプリングが必要なDEMかどうか判定する
    1: 5mDEMなら常に10mDEMにリサンプリング
    2: 1mDEMなら、画素数が所定の値よりも大きい場合に10mDEMにリサンプリング

    Args:
        dem_info (dict): ./utils.get_tiff_info()で取得できる辞書

    Returns:
        bool: 必要ならTrue
    """
    dem_resolution = dem_info.get("resolution", 10)
    if round(dem_resolution) == 10:
        return False
    elif round(dem_resolution) == 5:
        return True
    else:
        dem_size = dem_info.get("size", [0, 0])
        pixels_count = dem_size[0] * dem_size[1]
        return pixels_count > PIXELS_THRESHOLD_RESAMPLING
