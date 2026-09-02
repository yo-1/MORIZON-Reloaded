# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

import os
import math

import numpy as np
from osgeo import gdal

from ...settings_manager import SettingsManager
from ...constants import (
    OUTPUT_SITEIDX_SUGI,
    OUTPUT_SITEIDX_HINOKI,
    OUTPUT_SITEIDX_KARAMATSU
)

gdal.UseExceptions()

_DST_NODATA = -9999.0


def _dataset_info(path: str):
    ds = gdal.Open(path, gdal.GA_ReadOnly)
    if ds is None:
        raise RuntimeError(f"ラスターを開けません: {path}")
    gt = ds.GetGeoTransform()
    info = {
        "width": ds.RasterXSize,
        "height": ds.RasterYSize,
        "gt": gt,
        "projection": ds.GetProjection(),
        "xmin": gt[0],
        "xmax": gt[0] + gt[1] * ds.RasterXSize,
        "ymax": gt[3],
        "ymin": gt[3] + gt[5] * ds.RasterYSize,
    }
    ds = None
    return info


def _align_parameter_to_dem(reference_dem: str, source: str, output: str):
    """
    林野庁MORIZON仕様:
      - 解析DEMを基準グリッドとする
      - NPP/SRAD/VTEXは最近傍法
    QGIS Processing の TEMPORARY_OUTPUT を使用せず、GDAL Warpで直接GeoTIFF化する。
    """
    ref = _dataset_info(reference_dem)

    src_ds = gdal.Open(source, gdal.GA_ReadOnly)
    if src_ds is None:
        raise RuntimeError(f"入力パラメータラスターを開けません: {source}")

    src_band = src_ds.GetRasterBand(1)
    src_nodata = src_band.GetNoDataValue()

    os.makedirs(os.path.dirname(output), exist_ok=True)
    if os.path.exists(output):
        try:
            os.remove(output)
        except OSError:
            pass

    kwargs = dict(
        format="GTiff",
        dstSRS=ref["projection"],
        outputBounds=(ref["xmin"], ref["ymin"], ref["xmax"], ref["ymax"]),
        width=ref["width"],
        height=ref["height"],
        resampleAlg=gdal.GRA_NearestNeighbour,
        dstNodata=_DST_NODATA,
        multithread=True,
        creationOptions=["COMPRESS=LZW", "TILED=YES", "BIGTIFF=IF_SAFER"],
    )
    if src_nodata is not None:
        kwargs["srcNodata"] = src_nodata

    out_ds = gdal.Warp(output, src_ds, **kwargs)
    src_ds = None
    if out_ds is None:
        raise RuntimeError(f"パラメータラスターの整合に失敗しました: {source}")
    out_ds.FlushCache()
    out_ds = None

    if not os.path.exists(output):
        raise RuntimeError(f"整合済みラスターが作成されませんでした: {output}")

    chk = _dataset_info(output)
    if chk["width"] != ref["width"] or chk["height"] != ref["height"]:
        raise RuntimeError(
            f"整合後のグリッドサイズが一致しません: "
            f"DEM={ref['width']}x{ref['height']}, "
            f"target={chk['width']}x{chk['height']} : {output}"
        )
    return output


def _valid_mask(arr, nodata):
    mask = np.isfinite(arr)
    if nodata is not None and math.isfinite(float(nodata)):
        mask &= (arr != nodata)
    return mask


def _calculate_siteidx_blockwise(dem_path: str,
                                 npp_path: str,
                                 srad_path: str,
                                 vtex_path: str,
                                 output_path: str,
                                 p):
    """
    QgsRasterCalculator / Processing TEMPORARY_OUTPUTを使わず、
    GDALでブロック単位に林野庁版の地位指数式をそのまま計算する。

    QGIS設定値は文字列として保存されている場合があるため、
    演算前に必ず float へ正規化する。
    """
    try:
        p = [float(v) for v in p]
    except Exception as e:
        raise RuntimeError(
            f"地位指数パラメータを数値に変換できません: {p}"
        ) from e

    if len(p) != 7:
        raise RuntimeError(
            f"地位指数パラメータ数が不正です。期待値=7, 実際={len(p)}: {p}"
        )
    dem = gdal.Open(dem_path, gdal.GA_ReadOnly)
    npp = gdal.Open(npp_path, gdal.GA_ReadOnly)
    srad = gdal.Open(srad_path, gdal.GA_ReadOnly)
    vtex = gdal.Open(vtex_path, gdal.GA_ReadOnly)

    if any(ds is None for ds in (dem, npp, srad, vtex)):
        raise RuntimeError("地位計算用ラスターのオープンに失敗しました。")

    width, height = dem.RasterXSize, dem.RasterYSize
    for name, ds in (("NPP", npp), ("SRAD", srad), ("VTEX", vtex)):
        if ds.RasterXSize != width or ds.RasterYSize != height:
            raise RuntimeError(
                f"{name}のグリッドサイズが解析DEMと一致しません。"
                f" DEM={width}x{height}, {name}={ds.RasterXSize}x{ds.RasterYSize}"
            )

    driver = gdal.GetDriverByName("GTiff")
    if os.path.exists(output_path):
        try:
            os.remove(output_path)
        except PermissionError as e:
            raise RuntimeError(
                "既存の地位指数ラスターがWindowsでロックされています。"
                f"\n{output_path}\n{e}"
            ) from e
        except OSError as e:
            raise RuntimeError(
                f"既存の地位指数ラスターを削除できません。\n{output_path}\n{e}"
            ) from e

    out = driver.Create(
        output_path, width, height, 1, gdal.GDT_Float32,
        options=["COMPRESS=LZW", "TILED=YES", "BIGTIFF=IF_SAFER"]
    )
    if out is None:
        raise RuntimeError(f"地位指数ラスターを作成できません: {output_path}")

    out.SetGeoTransform(dem.GetGeoTransform())
    out.SetProjection(dem.GetProjection())
    ob = out.GetRasterBand(1)
    ob.SetNoDataValue(_DST_NODATA)

    db, nb, sb, vb = (
        dem.GetRasterBand(1), npp.GetRasterBand(1),
        srad.GetRasterBand(1), vtex.GetRasterBand(1)
    )
    dnd, nnd, snd, vnd = (
        db.GetNoDataValue(), nb.GetNoDataValue(),
        sb.GetNoDataValue(), vb.GetNoDataValue()
    )

    # メモリ使用量を抑えるため行ブロックで処理。
    block_rows = 256
    valid_count = 0
    min_val = float("inf")
    max_val = float("-inf")
    sum_val = 0.0

    for yoff in range(0, height, block_rows):
        rows = min(block_rows, height - yoff)

        d = db.ReadAsArray(0, yoff, width, rows).astype(np.float64, copy=False)
        a = nb.ReadAsArray(0, yoff, width, rows).astype(np.float64, copy=False)
        b = sb.ReadAsArray(0, yoff, width, rows).astype(np.float64, copy=False)
        c = vb.ReadAsArray(0, yoff, width, rows).astype(np.float64, copy=False)

        valid = (
            _valid_mask(d, dnd) &
            _valid_mask(a, nnd) &
            _valid_mask(b, snd) &
            _valid_mask(c, vnd)
        )

        result = np.full((rows, width), _DST_NODATA, dtype=np.float32)
        if np.any(valid):
            # 林野庁MORIZONの式を変更しない。
            values = (
                p[0]
                + (a[valid] - p[1]) * p[2]
                - (b[valid] - p[3]) * 0.01 * p[4]
                - (c[valid] - p[5]) * 0.01 * p[6]
            )
            finite = np.isfinite(values)
            if np.any(finite):
                valid_positions = np.flatnonzero(valid)
                good_positions = valid_positions[finite]
                flat = result.ravel()
                flat[good_positions] = values[finite].astype(np.float32)

                vv = values[finite]
                valid_count += vv.size
                min_val = min(min_val, float(vv.min()))
                max_val = max(max_val, float(vv.max()))
                sum_val += float(vv.sum())

        ob.WriteArray(result, 0, yoff)

    ob.FlushCache()
    out.FlushCache()
    out = None
    dem = npp = srad = vtex = None

    if valid_count == 0:
        raise RuntimeError(
            "地位指数の有効セルが0です。"
            "NPP/SRAD/VTEXと解析DEMの重なり範囲・CRS・NoDataを確認してください。"
        )

    mean_val = sum_val / valid_count
    if not all(math.isfinite(v) for v in (min_val, max_val, mean_val)):
        raise RuntimeError(
            f"地位指数の統計値がNaN/Infです。"
            f" Min={min_val}, Max={max_val}, Mean={mean_val}"
        )

    return output_path


def generate(basis_dem_filepath: str,
             npp_filepath: str,
             srad_filepath: str,
             vtex_filepath: str,
             output_dir: str) -> list:
    """
    林野庁MORIZON準拠の地位指数生成。
    解析仕様は維持し、QGIS 3.44/Windowsで不安定だった
    QgsRasterCalculatorとProcessing一時出力だけを使用しない。
    """
    os.makedirs(output_dir, exist_ok=True)
    aligned_dir = os.path.join(output_dir, "_morizon_work")
    os.makedirs(aligned_dir, exist_ok=True)

    adjusted_npp_filepath = _align_parameter_to_dem(
        basis_dem_filepath, npp_filepath,
        os.path.join(aligned_dir, "siteidx_npp_aligned.tif")
    )
    adjusted_srad_filepath = _align_parameter_to_dem(
        basis_dem_filepath, srad_filepath,
        os.path.join(aligned_dir, "siteidx_srad_aligned.tif")
    )
    adjusted_vtex_filepath = _align_parameter_to_dem(
        basis_dem_filepath, vtex_filepath,
        os.path.join(aligned_dir, "siteidx_vtex_aligned.tif")
    )

    smanager = SettingsManager()
    settings = smanager.get_settings()

    outputs = (
        (os.path.join(output_dir, OUTPUT_SITEIDX_SUGI["FILE_NAME"] + ".tif"),
         settings["siteidx_sugi_params"]),
        (os.path.join(output_dir, OUTPUT_SITEIDX_HINOKI["FILE_NAME"] + ".tif"),
         settings["siteidx_hinoki_params"]),
        (os.path.join(output_dir, OUTPUT_SITEIDX_KARAMATSU["FILE_NAME"] + ".tif"),
         settings["siteidx_karamatsu_params"]),
    )

    for output_filepath, params in outputs:
        _calculate_siteidx_blockwise(
            basis_dem_filepath,
            adjusted_npp_filepath,
            adjusted_srad_filepath,
            adjusted_vtex_filepath,
            output_filepath,
            params
        )

    return tuple(path for path, _ in outputs)
