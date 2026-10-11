# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

"""
O-07: 再配布可能な最小回帰データセットを生成するスクリプト（test_data/ZoningKit_SYNTH）。

実際の地理データ（Zoningkit_SAMPLE等）は再配布権が未確認のため、このスクリプトは
地形・建物・路網・作業システムCSVをすべて数式・固定値から合成する。実在する地点の
地形や施設情報とは一切関係が無く、著作権・測量成果物としての権利関係の懸念がない。

出力先（test_data/ZoningKit_SYNTH/）は、docs/HANDOFF.md「5. 入力データとフォルダ契約」
の構造（DATA/DEM, DATA/ROAD, DATA/SAGYO-SYSTEM_CSV, DATA/SiteIndex/{NPP,SRAD,VTEX},
DATA/TATEMONO）に合わせている。

実行方法（Linux開発環境、QGIS不要。GDAL/OGR Pythonバインディングが必要）:
    python3 scripts/generate_regression_test_data.py

このスクリプトは入力データのみを生成する。MORIZON本体での実行・しきい値・出力値の
「受入済み基準（accepted reference run）」は、QGIS実機で実際に処理を1回実行し、
その結果を人が確認・承認した上で docs/TEST_RECORD.md に記録することを想定している
（Definition of doneの「Output names, grid, CRS, ... match the accepted reference
run」は、このデータだけでなく、実機での承認という人の判断を必要とする）。
"""

import os
import numpy as np
from osgeo import gdal, ogr, osr

gdal.UseExceptions()
ogr.UseExceptions()

# JGD2000 / Japan Plane Rectangular CS IX（本州中部〜関東付近を想定した平面直角座標系）。
# 実在の地点とは無関係の、仮の原点まわりの合成地形に適用する。
EPSG = 6677

OUT_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "test_data",
    "ZoningKit_SYNTH",
    "DATA",
)

WIDTH, HEIGHT = (
    80,
    60,
)  # セル数（10m解像度で800m x 600m相当、Zoningkit_SAMPLEの1/10スケール）
CELL = 10.0
ORIGIN_X, ORIGIN_Y_TOP = (
    0.0,
    HEIGHT * CELL,
)  # 左上原点（北がY+、GDAL標準のnorth-up）


def _srs():
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(EPSG)
    return srs


def _write_raster(path, array, nodata=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    driver = gdal.GetDriverByName("GTiff")
    h, w = array.shape
    ds = driver.Create(
        path, w, h, 1, gdal.GDT_Float32, options=["COMPRESS=LZW"]
    )
    ds.SetGeoTransform([ORIGIN_X, CELL, 0.0, ORIGIN_Y_TOP, 0.0, -CELL])
    ds.SetProjection(_srs().ExportToWkt())
    band = ds.GetRasterBand(1)
    if nodata is not None:
        band.SetNoDataValue(nodata)
    band.WriteArray(array.astype(np.float32))
    band.FlushCache()
    ds = None
    print(f"  wrote {path}  shape={
        array.shape}  min={
            array.min():.3f} max={
                array.max():.3f}")


def generate_dem():
    """滑らかで起伏のある合成DEM。平地・尾根・谷を模した形状（実在地形とは無関係）。"""
    x = (np.arange(WIDTH) + 0.5) * CELL
    y = (np.arange(HEIGHT) + 0.5) * CELL
    X, Y = np.meshgrid(x, y)
    Z = (
        300.0
        + 120.0 * np.sin(X / 260.0) * np.cos(Y / 220.0)
        + 0.0009 * (X - 400.0) ** 2
        - 0.0006 * (Y - 300.0) ** 2
        + 25.0 * np.sin(X / 70.0 + Y / 95.0)
    ).astype(np.float32)
    # 標高が負にならないよう底上げ（森林地形として不自然な値を避ける）
    Z = Z - Z.min() + 50.0
    return Z[::-1, :]  # north-up: 配列の先頭行が北側(Y最大)になるよう反転


def generate_siteidx_inputs():
    """地位指数の入力（NPP・日射係数・凹凸度）を、DEMと緩く相関する合成値で作る。"""
    x = (np.arange(WIDTH) + 0.5) * CELL
    y = (np.arange(HEIGHT) + 0.5) * CELL
    X, Y = np.meshgrid(x, y)
    npp = (
        1200.0 + 150.0 * np.sin(X / 180.0) + 80.0 * np.cos(Y / 140.0)
    ).astype(np.float32)
    srad = (4200.0 + 300.0 * np.cos(X / 220.0 + Y / 260.0)).astype(np.float32)
    vtex = (18.0 + 6.0 * np.sin(X / 150.0) * np.sin(Y / 130.0)).astype(
        np.float32
    )
    return npp[::-1, :], srad[::-1, :], vtex[::-1, :]


def generate_building_polygons(path):
    """建物ポリゴン（保全対象）を3棟分、DEM範囲内に合成配置する。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    drv = ogr.GetDriverByName("ESRI Shapefile")
    if os.path.exists(path):
        drv.DeleteDataSource(path)
    ds = drv.CreateDataSource(path)
    layer = ds.CreateLayer("tatemono", _srs(), ogr.wkbPolygon)
    layer.CreateField(ogr.FieldDefn("id", ogr.OFTInteger))

    def _square(cx, cy, half):
        ring = ogr.Geometry(ogr.wkbLinearRing)
        ring.AddPoint(cx - half, cy - half)
        ring.AddPoint(cx + half, cy - half)
        ring.AddPoint(cx + half, cy + half)
        ring.AddPoint(cx - half, cy + half)
        ring.AddPoint(cx - half, cy - half)
        poly = ogr.Geometry(ogr.wkbPolygon)
        poly.AddGeometry(ring)
        return poly

    buildings = [
        (150.0, 450.0, 15.0),
        (420.0, 200.0, 12.0),
        (620.0, 480.0, 18.0),
    ]
    for i, (cx, cy, half) in enumerate(buildings):
        feat = ogr.Feature(layer.GetLayerDefn())
        feat.SetField("id", i + 1)
        feat.SetGeometry(_square(cx, cy, half))
        layer.CreateFeature(feat)
        feat = None
    ds = None
    print(f"  wrote {path}  features={len(buildings)}")


def generate_road_lines(path):
    """既設路網ライン。DEM範囲を縦断・横断する2本の折れ線（DEM範囲内に収まる）。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    drv = ogr.GetDriverByName("ESRI Shapefile")
    if os.path.exists(path):
        drv.DeleteDataSource(path)
    ds = drv.CreateDataSource(path)
    layer = ds.CreateLayer("romou", _srs(), ogr.wkbLineString)
    layer.CreateField(ogr.FieldDefn("id", ogr.OFTInteger))

    lines = [
        [(20.0, 20.0), (300.0, 150.0), (500.0, 100.0), (770.0, 180.0)],
        [(100.0, 580.0), (250.0, 400.0), (400.0, 350.0), (400.0, 60.0)],
    ]
    for i, pts in enumerate(lines):
        geom = ogr.Geometry(ogr.wkbLineString)
        for px, py in pts:
            geom.AddPoint(px, py)
        feat = ogr.Feature(layer.GetLayerDefn())
        feat.SetField("id", i + 1)
        feat.SetGeometry(geom)
        layer.CreateFeature(feat)
        feat = None
    ds = None
    print(f"  wrote {path}  features={len(lines)}")


def generate_sagyo_system_csv(path):
    """
    作業システムCSV。processes/costcsv_parser.py のdocstringに記載されている
    実例の数値（元MORIZONの構造説明用サンプルであり、GPL-3.0-onlyの本リポジトリ
    に既に含まれる値）をそのまま使用する。新規の著作物性のある数値を作らない。
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rows = [
        ["550", "10", "15", "20", "25", "30", "35", "40"],
        ["500", "0", "0", "7", "2", "2", "2", ""],
        ["450", "0", "0", "7", "2", "2", "2", ""],
        ["400", "0", "0", "7", "2", "2", "2", ""],
        ["350", "0", "7", "7", "5", "2", "2", ""],
        ["300", "0", "7", "7", "5", "2", "2", ""],
        ["250", "10", "8", "7", "5", "3", "2", ""],
        ["200", "10", "8", "7", "5", "3", "2", ""],
        ["150", "10", "9", "8", "6", "4", "0", ""],
        ["100", "10", "9", "8", "6", "4", "0", ""],
        ["50", "10", "9", "9", "0", "0", "0", ""],
        [""],
        [""],
        [""],
        ["code", "name"],
        ["10", "CTL"],
        ["9", "9-13tグラップル"],
        ["8", "9-13tウィンチ"],
        ["7", "9-13tスイングヤーダ"],
        ["6", "6-8tウィンチ"],
        ["5", "6-8tスイングヤーダ"],
        ["4", "3-4tウィンチ"],
        ["3", "タワーヤーダ"],
        ["2", "本架線"],
        ["1", "該当なし"],
        ["0", "該当なし"],
    ]
    import csv

    with open(path, "w", encoding="cp932", newline="") as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(row)
    print(f"  wrote {path}  rows={len(rows)}")


def main():
    print("=== O-07: 回帰テスト用合成データセット生成 ===")
    print(f"出力先: {OUT_ROOT}")

    print("DEM...")
    dem = generate_dem()
    _write_raster(os.path.join(OUT_ROOT, "DEM", "DEM_SYNTH.tif"), dem)

    print("地位指数入力(NPP/SRAD/VTEX)...")
    npp, srad, vtex = generate_siteidx_inputs()
    _write_raster(
        os.path.join(OUT_ROOT, "SiteIndex", "NPP", "NPP_SYNTH.tif"), npp
    )
    _write_raster(
        os.path.join(OUT_ROOT, "SiteIndex", "SRAD", "SRAD_SYNTH.tif"), srad
    )
    _write_raster(
        os.path.join(OUT_ROOT, "SiteIndex", "VTEX", "VTEX_SYNTH.tif"), vtex
    )

    print("建物ポリゴン...")
    generate_building_polygons(
        os.path.join(OUT_ROOT, "TATEMONO", "tatemono_SYNTH.shp")
    )

    print("既設路網ライン...")
    generate_road_lines(os.path.join(OUT_ROOT, "ROAD", "romou_SYNTH.shp"))

    print("作業システムCSV...")
    generate_sagyo_system_csv(
        os.path.join(OUT_ROOT, "SAGYO-SYSTEM_CSV", "sagyou_SYNTH.csv")
    )

    print("=== 完了 ===")


if __name__ == "__main__":
    main()
