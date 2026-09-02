# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

import os
import tempfile

import numpy as np
from osgeo import gdal

from qgis.core import QgsRasterLayer, QgsVectorLayer

from ...constants import OUTPUT_DISTANCE


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


def generate(basis_dem_filepath: str,
             line_vector_filepath: str,
             output_dir: str) -> str:
    """
    林野庁MORIZON「地利」用の既設路網からの直線距離ラスターを生成する。

    QGIS 3.44安定化方針:
      * 解析グリッドは basis_dem_filepath（MORIZONの10m解析DEM）に完全一致
      * 路網を同じ行列・extent・CRSへ直接ラスタライズ
      * 距離は GDAL ComputeProximity の GEO（地図単位）でユークリッド距離
      * DEMのNoData領域は出力でも -9999 NoData
      * QgsRasterCalculator / grass7:r.grow.distance は使用しない

    平面直角座標系（メートル）では、従来の r.grow.distance -m,
    metric=euclidean と同じ意味の「路網までの平面ユークリッド距離[m]」になる。
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

    try:
        driver = gdal.GetDriverByName("GTiff")
        mask_ds = driver.Create(
            mask_path, width, height, 1, gdal.GDT_Byte,
            options=["TILED=YES", "COMPRESS=LZW", "BIGTIFF=IF_SAFER"]
        )
        if mask_ds is None:
            raise RuntimeError("地利計算用の路網ラスターを作成できません。")

        mask_ds.SetGeoTransform(gt)
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

        # 距離出力をDEMと完全同一グリッドで作成。
        if os.path.exists(output_filepath):
            try:
                os.remove(output_filepath)
            except PermissionError as e:
                raise RuntimeError(
                    "既存の地利ラスターがWindowsでロックされています。"
                    f"\n{output_filepath}\n{e}"
                ) from e
            except OSError as e:
                raise RuntimeError(
                    f"既存の地利ラスターを削除できません。\n{output_filepath}\n{e}"
                ) from e

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

        # DISTUNITS=GEO: 平面直角座標系なら単位はm。
        err = gdal.ComputeProximity(
            mask_ds.GetRasterBand(1),
            dist_band,
            options=["VALUES=1", "DISTUNITS=GEO"]
        )
        if err != 0:
            raise RuntimeError("既設路網からの距離計算に失敗しました。")

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
        try:
            mask_ds = None
        except Exception:
            pass
        try:
            if os.path.exists(mask_path):
                os.remove(mask_path)
        except OSError:
            pass
