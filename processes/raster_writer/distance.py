# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

import math
import os
import tempfile

import numpy as np
from osgeo import gdal

from qgis.core import QgsRasterLayer, QgsVectorLayer

from ...constants import OUTPUT_DISTANCE
from .utils import resolve_writable_output_path


NODATA_DISTANCE = -9999.0


def _dataset_path(ds):
    """Return a filesystem path for a GDAL dataset, if available."""
    try:
        return ds.GetDescription()
    except Exception:
        return ""


def _same_grid(a, b, tolerance=1.0e-9):
    if a.RasterXSize != b.RasterXSize or a.RasterYSize != b.RasterYSize:
        return False
    gta = a.GetGeoTransform()
    gtb = b.GetGeoTransform()
    return all(abs(float(x) - float(y)) <= tolerance for x, y in zip(gta, gtb))


def _snap_down(value, origin, step):
    n = math.floor((value - origin) / step + 1.0e-9)
    return origin + n * step


def _snap_up(value, origin, step):
    n = math.ceil((value - origin) / step - 1.0e-9)
    return origin + n * step


def generate(basis_dem_filepath: str,
             line_vector_filepath: str,
             output_dir: str) -> str:
    """
    林野庁MORIZON「地利」用の既設路網からの直線距離ラスターを生成する。

    QGIS 3.44安定化方針:
      * 距離計算は DEM extent と路網 extent の和集合グリッド（DEMと同じ解像度、
        DEMのピクセル格子に整列）上で行う。路網がDEM extentの外側へ一部でも
        はみ出す場合、路網を直接DEMグリッドへラスタライズすると焼き込み対象
        ピクセルが0になり、GDALの「対象ピクセルなし」センチネル値（実測65535）
        が出力全体を埋めてしまう不具合があったため（O-23、2026-10-09）。
        元MORIZONの grass7:r.grow.distance も、DEMと路網extentの和集合グリッド
        で計算してからDEMグリッドへ再サンプリングしていた。
      * 距離は GDAL ComputeProximity の GEO（地図単位）でユークリッド距離
      * 和集合グリッドはDEMと同一解像度・同一ピクセル格子に整列しているため、
        DEM範囲の切り出しは再サンプリングではなく整数ピクセル単位のクロップで行う
        （補間による誤差が入らない）
      * DEMのNoData領域は出力でも -9999 NoData
      * QgsRasterCalculator / grass7:r.grow.distance は使用しない

    平面直角座標系（メートル）では、従来の r.grow.distance -m,
    metric=euclidean と同じ意味の「路網までの平面ユークリッド距離[m]」になる。
    O-23の検証（合成DEM・実GRASS r.grow.distanceとの比較）で、和集合グリッド上
    であればGDAL ComputeProximityと実GRASSの出力が最大差0.0001m未満で一致する
    ことを確認済み（docs/OPEN_ISSUES.md参照）。
    """
    os.makedirs(output_dir, exist_ok=True)

    dem_ds = gdal.Open(str(basis_dem_filepath), gdal.GA_ReadOnly)
    if dem_ds is None:
        raise RuntimeError(f"解析DEMを開けません: {basis_dem_filepath}")

    vector_layer = QgsVectorLayer(str(line_vector_filepath), "network", "ogr")
    if not vector_layer.isValid():
        dem_ds = None
        raise RuntimeError(f"既設路網ラインを開けません: {line_vector_filepath}")

    if vector_layer.featureCount() <= 0:
        dem_ds = None
        raise RuntimeError("既設路網ラインに地物がありません。")

    # MORIZON標準データはDEMとROADが同一CRS。
    # 誤った距離計算を防ぐため、異なる場合は明示的に停止する。
    dem_wkt = dem_ds.GetProjection()
    dem_layer = QgsRasterLayer(str(basis_dem_filepath), "dem_for_chiri")
    if dem_layer.isValid() and vector_layer.crs().isValid() and dem_layer.crs().isValid():
        if vector_layer.crs() != dem_layer.crs():
            dem_ds = None
            raise RuntimeError(
                "DEMと既設路網ラインのCRSが一致していません。"
                f" DEM={dem_layer.crs().authid()}, ROAD={vector_layer.crs().authid()}。"
                "MORIZON地利計算では同一の平面直角座標系にしてください。"
            )

    gt = dem_ds.GetGeoTransform()
    width = dem_ds.RasterXSize
    height = dem_ds.RasterYSize
    res_x = abs(gt[1])
    res_y = abs(gt[5])
    dem_xmin = gt[0]
    dem_ymax = gt[3]
    dem_xmax = dem_xmin + res_x * width
    dem_ymin = dem_ymax - res_y * height

    # O-23: 路網がDEM extentの外側へはみ出す場合に備え、DEM extentと路網extentの
    # 和集合を、DEMのピクセル格子に整列させた上で計算グリッドとする。
    road_extent = vector_layer.extent()
    union_xmin = _snap_down(min(dem_xmin, road_extent.xMinimum()), dem_xmin, res_x)
    union_xmax = _snap_up(max(dem_xmax, road_extent.xMaximum()), dem_xmin, res_x)
    union_ymin = _snap_down(min(dem_ymin, road_extent.yMinimum()), dem_ymin, res_y)
    union_ymax = _snap_up(max(dem_ymax, road_extent.yMaximum()), dem_ymin, res_y)

    union_width = int(round((union_xmax - union_xmin) / res_x))
    union_height = int(round((union_ymax - union_ymin) / res_y))
    union_gt = (union_xmin, res_x, 0.0, union_ymax, 0.0, -res_y)

    # DEMグリッドは和集合グリッドの整数ピクセル位置に整列しているはず。
    col_offset = int(round((dem_xmin - union_xmin) / res_x))
    row_offset = int(round((union_ymax - dem_ymax) / res_y))
    if (
        col_offset < 0 or row_offset < 0
        or col_offset + width > union_width
        or row_offset + height > union_height
    ):
        dem_ds = None
        raise RuntimeError(
            "地利計算用の和集合グリッドにDEM範囲を整合できませんでした。"
            f" col_offset={col_offset}, row_offset={row_offset},"
            f" union={union_width}x{union_height}, dem={width}x{height}"
        )

    output_filepath = os.path.join(
        output_dir, OUTPUT_DISTANCE["FILE_NAME"] + ".tif"
    )

    # 一時ファイルもQGISのTEMPではなく出力先近傍へ置く。
    # Windows/QGISでTEMPパスに起因する不安定性を避ける。
    fd, mask_path = tempfile.mkstemp(
        prefix="_morizon_chiri_road_", suffix=".tif", dir=output_dir
    )
    os.close(fd)
    try:
        os.remove(mask_path)
    except OSError:
        pass
    fd, union_dist_path = tempfile.mkstemp(
        prefix="_morizon_chiri_dist_union_", suffix=".tif", dir=output_dir
    )
    os.close(fd)
    try:
        os.remove(union_dist_path)
    except OSError:
        pass

    try:
        driver = gdal.GetDriverByName("GTiff")
        mask_ds = driver.Create(
            mask_path, union_width, union_height, 1, gdal.GDT_Byte,
            options=["TILED=YES", "COMPRESS=LZW", "BIGTIFF=IF_SAFER"]
        )
        if mask_ds is None:
            raise RuntimeError("地利計算用の路網ラスターを作成できません。")

        mask_ds.SetGeoTransform(union_gt)
        mask_ds.SetProjection(dem_wkt)
        mask_band = mask_ds.GetRasterBand(1)
        mask_band.SetNoDataValue(0)
        mask_band.Fill(0)

        # GDAL Rasterize APIを使用。ALL_TOUCHED=TRUEで10mセル上の細い路網を落としにくくする。
        vec_ds = gdal.OpenEx(str(line_vector_filepath), gdal.OF_VECTOR)
        if vec_ds is None:
            raise RuntimeError(f"既設路網ラインをGDALで開けません: {line_vector_filepath}")
        layer = vec_ds.GetLayer(0)
        err = gdal.RasterizeLayer(
            mask_ds, [1], layer, burn_values=[1],
            options=["ALL_TOUCHED=TRUE"]
        )
        vec_ds = None
        mask_band.FlushCache()
        mask_ds.FlushCache()
        if err != 0:
            raise RuntimeError("既設路網ラインの10mラスタライズに失敗しました。")

        mask_stats = mask_band.GetStatistics(False, True)
        if not mask_stats or mask_stats[1] is None or mask_stats[1] <= 0:
            raise RuntimeError(
                "既設路網ラインが和集合グリッド上に1ピクセルも焼き込まれませんでした。"
                "路網データのCRS・ジオメトリを確認してください。"
            )

        # 距離計算は和集合グリッド上で行い、DISTUNITS=GEOでユークリッド距離を求める。
        union_dist_ds = driver.Create(
            union_dist_path, union_width, union_height, 1, gdal.GDT_Float32,
            options=["TILED=YES", "COMPRESS=LZW", "BIGTIFF=IF_SAFER"]
        )
        if union_dist_ds is None:
            raise RuntimeError("地利計算用の和集合距離ラスターを作成できません。")
        union_dist_ds.SetGeoTransform(union_gt)
        union_dist_ds.SetProjection(dem_wkt)
        union_dist_band = union_dist_ds.GetRasterBand(1)
        union_dist_band.SetNoDataValue(NODATA_DISTANCE)

        err = gdal.ComputeProximity(
            mask_band,
            union_dist_band,
            options=["VALUES=1", "DISTUNITS=GEO"]
        )
        if err != 0:
            raise RuntimeError("既設路網からの距離計算に失敗しました。")
        union_dist_band.FlushCache()
        union_dist_ds.FlushCache()

        # 和集合グリッドはDEMと同一解像度・同一ピクセル格子に整列しているため、
        # DEM範囲は再サンプリングではなく整数ピクセル単位のクロップで取り出せる。
        cropped = union_dist_band.ReadAsArray(col_offset, row_offset, width, height)
        if cropped is None:
            raise RuntimeError("地利計算結果からDEM範囲を切り出せませんでした。")

        # 距離出力をDEMと完全同一グリッドで作成。
        # STEP: 他のwriter（savearea/shc/risk/profit/zoning）と同じく、
        # 既存出力がWindowsでロックされていても処理を中断せず、
        # 世代付きファイル（_v2, _v3, ...）へ安全に退避する。
        output_filepath = resolve_writable_output_path(output_filepath)

        dist_ds = driver.Create(
            output_filepath, width, height, 1, gdal.GDT_Float32,
            options=["TILED=YES", "COMPRESS=LZW", "BIGTIFF=IF_SAFER"]
        )
        if dist_ds is None:
            raise RuntimeError(f"地利計算ラスターを作成できません: {output_filepath}")

        dist_ds.SetGeoTransform(gt)
        dist_ds.SetProjection(dem_wkt)
        dist_band = dist_ds.GetRasterBand(1)
        dist_band.SetNoDataValue(NODATA_DISTANCE)
        dist_band.WriteArray(np.asarray(cropped, dtype=np.float32))
        dist_band.FlushCache()

        union_dist_band = None
        union_dist_ds = None

        # DEM NoDataを距離結果へ継承。大容量でもメモリを使い過ぎないようブロック処理。
        dem_band = dem_ds.GetRasterBand(1)
        dem_nodata = dem_band.GetNoDataValue()
        block_x, block_y = dem_band.GetBlockSize()
        if not block_x or block_x <= 0:
            block_x = min(1024, width)
        if not block_y or block_y <= 0:
            block_y = min(512, height)

        if dem_nodata is not None:
            for yoff in range(0, height, block_y):
                ysize = min(block_y, height - yoff)
                for xoff in range(0, width, block_x):
                    xsize = min(block_x, width - xoff)
                    dem_arr = dem_band.ReadAsArray(xoff, yoff, xsize, ysize)
                    dist_arr = dist_band.ReadAsArray(xoff, yoff, xsize, ysize)
                    if dem_arr is None or dist_arr is None:
                        raise RuntimeError("地利計算ラスターのブロック読み込みに失敗しました。")
                    dist_arr = np.asarray(dist_arr, dtype=np.float32)
                    if np.isnan(dem_nodata):
                        invalid = np.isnan(dem_arr)
                    else:
                        invalid = np.isclose(
                            np.asarray(dem_arr, dtype=np.float64),
                            float(dem_nodata),
                            rtol=0.0, atol=1.0e-12
                        )
                    dist_arr[invalid] = np.float32(NODATA_DISTANCE)
                    dist_band.WriteArray(dist_arr, xoff, yoff)

        dist_band.FlushCache()
        dist_ds.FlushCache()

        if not _same_grid(dem_ds, dist_ds):
            raise RuntimeError("地利計算結果のグリッドが解析DEMと一致しません。")

        # 明示的に閉じてからQGIS側が読み込める状態にする。
        dist_band = None
        dist_ds = None
        mask_band = None
        mask_ds = None
        dem_ds = None

        check = gdal.Open(output_filepath, gdal.GA_ReadOnly)
        if check is None:
            raise RuntimeError(f"地利計算ラスターを開けません: {output_filepath}")
        band = check.GetRasterBand(1)
        stats = band.GetStatistics(False, True)
        check = None
        if stats is None:
            raise RuntimeError("地利計算結果の統計値を取得できません。")

        return output_filepath

    finally:
        dem_ds = None
        mask_ds = None
        try:
            if os.path.exists(mask_path):
                os.remove(mask_path)
        except OSError:
            pass
        try:
            if os.path.exists(union_dist_path):
                os.remove(union_dist_path)
        except OSError:
            pass
