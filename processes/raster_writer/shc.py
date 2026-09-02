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
from ...constants import OUTPUT_SHC

gdal.UseExceptions()

_NODATA = -9999.0


def _read_dem(path):
    ds = gdal.Open(path, gdal.GA_ReadOnly)
    if ds is None:
        raise RuntimeError(f"解析DEMを開けません: {path}")
    band = ds.GetRasterBand(1)
    arr = band.ReadAsArray().astype(np.float64, copy=False)
    nd = band.GetNoDataValue()

    valid = np.isfinite(arr)
    if nd is not None:
        if np.isnan(float(nd)):
            valid &= ~np.isnan(arr)
        else:
            valid &= ~np.isclose(arr, float(nd), rtol=0.0, atol=1.0e-12)

    return ds, arr, valid


def _conv_axis_same(arr, kernel, axis):
    """
    NumPyだけで行う1次元畳み込み。
    QGIS同梱PythonにSciPyが無い環境でも動作するようにする。
    """
    arr = np.asarray(arr, dtype=np.float64)
    out = np.empty_like(arr, dtype=np.float64)

    if axis == 1:
        for y in range(arr.shape[0]):
            out[y, :] = np.convolve(arr[y, :], kernel, mode="same")
    else:
        for x in range(arr.shape[1]):
            out[:, x] = np.convolve(arr[:, x], kernel, mode="same")

    return out


def _gaussian_smooth(arr, valid, sigma=3.0, radius=12):
    """
    元MORIZON / SAGA 2.3.x:
      saga:gaussianfilter MODE=1, RADIUS=12, SIGMA=3

    MODE=1 は「円形」検索窓である。
    旧Reloadedでは分離可能なX/Y Gaussianを用いたため、実質的に正方形窓となり、
    SHCが旧MORIZONより系統的に小さくなる問題があった。

    ここでは半径radiusセルの円内だけをGaussian重み付き平均し、
    NoDataは重みから除外して正規化する。
    SciPyには依存せずNumPyだけで実装する。
    """
    arr = np.asarray(arr, dtype=np.float64)
    valid = np.asarray(valid, dtype=bool)

    h, w = arr.shape
    numerator = np.zeros((h, w), dtype=np.float64)
    denominator = np.zeros((h, w), dtype=np.float64)

    base_data = np.where(valid, arr, 0.0)
    base_weight = valid.astype(np.float64)

    # 円形カーネルをdyごとの水平Gaussianとして計算する。
    for dy in range(-radius, radius + 1):
        rx = int(math.floor(math.sqrt(max(0, radius * radius - dy * dy))))
        xs = np.arange(-rx, rx + 1, dtype=np.float64)

        # 2D Gaussian exp(-(x^2+y^2)/(2*sigma^2))
        kernel_x = np.exp(
            -(xs * xs + float(dy * dy)) / (2.0 * sigma * sigma)
        )

        row_num = _conv_axis_same(base_data, kernel_x, axis=1)
        row_den = _conv_axis_same(base_weight, kernel_x, axis=1)

        if dy < 0:
            # source y -> destination y-dy
            numerator[-dy:, :] += row_num[:h + dy, :]
            denominator[-dy:, :] += row_den[:h + dy, :]
        elif dy > 0:
            numerator[:-dy, :] += row_num[dy:, :]
            denominator[:-dy, :] += row_den[dy:, :]
        else:
            numerator += row_num
            denominator += row_den

    smoothed = np.full(arr.shape, np.nan, dtype=np.float64)
    good = denominator > 1.0e-12
    smoothed[good] = numerator[good] / denominator[good]
    return smoothed, good


def _plan_curvature_zevenbergen(smoothed, valid, cellsize):
    """
    元MORIZONの SAGA Slope, Aspect, Curvature METHOD=6
    = Zevenbergen & Thorne (1987) のPlan Curvatureを再現する。

    旧MORIZONが利用したSAGA 2.x系の Set_Zevenbergen / Set_From_Polynom の係数処理を再現。
    """
    z = smoothed
    out = np.full(z.shape, np.nan, dtype=np.float64)

    c  = z[1:-1, 1:-1]
    n  = z[:-2,  1:-1]
    s_ = z[2:,   1:-1]
    w  = z[1:-1, :-2]
    e  = z[1:-1, 2:]
    nw = z[:-2,  :-2]
    ne = z[:-2,  2:]
    sw = z[2:,   :-2]
    se = z[2:,   2:]

    v = (
        valid[1:-1, 1:-1] &
        valid[:-2, 1:-1] & valid[2:, 1:-1] &
        valid[1:-1, :-2] & valid[1:-1, 2:] &
        valid[:-2, :-2] & valid[:-2, 2:] &
        valid[2:, :-2] & valid[2:, 2:]
    )

    cellarea = cellsize * cellsize

    # SAGA Get_SubMatrix3x3 orientation=0:
    # Z5=N, Z3=S, Z1=W, Z7=E, Z0=SW, Z2=NW, Z6=SE, Z8=NE.
    r = (((s_ - c) + (n - c)) / 2.0) / cellarea
    t = (((w - c) + (e - c)) / 2.0) / cellarea
    ss = ((sw - c) - (nw - c) - (se - c) + (ne - c)) / (4.0 * cellarea)
    p = ((n - c) - (s_ - c)) / (2.0 * cellsize)
    q = ((e - c) - (w - c)) / (2.0 * cellsize)

    # Legacy SAGA 2.x compatibility:
    # 旧MORIZONが利用していたSAGAのMorphometry実装では、
    # Set_From_Polynom() 内で二次微分係数 r, t を2倍してから
    # plan curvature等を評価する版が用いられていた。
    # Zevenbergen式の係数D/Eは「2次項係数 (= 2階微分の1/2)」なので、
    # 旧SAGAの実装挙動に合わせてここで2倍する。
    r *= 2.0
    t *= 2.0

    p2q2 = p * p + q * q
    good = v & np.isfinite(p2q2) & (p2q2 > 0.0)

    plan = np.full(c.shape, np.nan, dtype=np.float64)
    numerator = -(t * p * p + r * q * q - 2.0 * ss * p * q)
    plan[good] = numerator[good] / np.power(p2q2[good], 1.5)

    out[1:-1, 1:-1] = plan
    return out, np.isfinite(out)


def _horizontal_sum(arr, radius):
    """各行について左右radiusセルの合計を返す。境界は利用可能範囲のみ。"""
    if radius <= 0:
        return arr.copy()
    padded = np.pad(arr, ((0, 0), (radius, radius)), mode="constant")
    cs = np.cumsum(padded, axis=1, dtype=np.float64)
    cs = np.pad(cs, ((0, 0), (1, 0)), mode="constant")
    width = arr.shape[1]
    return cs[:, 2 * radius + 1:2 * radius + 1 + width] - cs[:, :width]


def _circular_std(arr, valid, size):
    """
    元MORIZON:
      grass7:r.neighbors method=6, -c=True, size=shc_param

    円形近傍の標準偏差（population standard deviation）をNumPyで計算する。
    size=49なら半径24セル。
    """
    if size < 3 or size % 2 == 0:
        raise RuntimeError(f"SHC計算範囲は3以上の奇数である必要があります: {size}")

    radius = (size - 1) // 2
    values = np.where(valid, arr, 0.0)
    values2 = values * values
    weights = valid.astype(np.float64)

    total = np.zeros(arr.shape, dtype=np.float64)
    total2 = np.zeros(arr.shape, dtype=np.float64)
    count = np.zeros(arr.shape, dtype=np.float64)

    for dy in range(-radius, radius + 1):
        rx = int(math.floor(math.sqrt(max(0, radius * radius - dy * dy))))

        hs = _horizontal_sum(values, rx)
        hs2 = _horizontal_sum(values2, rx)
        hc = _horizontal_sum(weights, rx)

        if dy < 0:
            total[-dy:, :] += hs[:arr.shape[0] + dy, :]
            total2[-dy:, :] += hs2[:arr.shape[0] + dy, :]
            count[-dy:, :] += hc[:arr.shape[0] + dy, :]
        elif dy > 0:
            total[:-dy, :] += hs[dy:, :]
            total2[:-dy, :] += hs2[dy:, :]
            count[:-dy, :] += hc[dy:, :]
        else:
            total += hs
            total2 += hs2
            count += hc

    out = np.full(arr.shape, np.nan, dtype=np.float64)
    good = count > 0.0
    mean = np.zeros(arr.shape, dtype=np.float64)
    mean2 = np.zeros(arr.shape, dtype=np.float64)
    mean[good] = total[good] / count[good]
    mean2[good] = total2[good] / count[good]
    variance = mean2 - mean * mean
    variance[variance < 0.0] = 0.0
    out[good] = np.sqrt(variance[good])

    return out, good


def _write_like(reference_path, output_path, arr, valid):
    ref = gdal.Open(reference_path, gdal.GA_ReadOnly)
    if ref is None:
        raise RuntimeError(f"基準DEMを開けません: {reference_path}")

    # QGIS/Windowsでは、表示中のGeoTIFFがGDAL/QGIS側でファイルロックされ、
    # 同名ファイルを削除・上書きできない場合がある。
    # 解析を中断させず、ロック時だけ _v2, _v3 ... の世代ファイルへ退避する。
    # スコアリング側の自動選択は世代サフィックスを認識し、最新版を優先する。
    requested_output_path = output_path
    if os.path.exists(output_path):
        try:
            os.remove(output_path)
        except (PermissionError, OSError):
            base, ext = os.path.splitext(output_path)
            generation = 2
            while True:
                candidate = f"{base}_v{generation}{ext}"
                if not os.path.exists(candidate):
                    output_path = candidate
                    break
                try:
                    os.remove(candidate)
                    output_path = candidate
                    break
                except (PermissionError, OSError):
                    generation += 1
                    if generation > 999:
                        raise RuntimeError(
                            "地形の複雑さラスターの出力先を確保できません。"
                        )

    drv = gdal.GetDriverByName("GTiff")
    out = drv.Create(
        output_path, ref.RasterXSize, ref.RasterYSize, 1, gdal.GDT_Float32,
        options=["TILED=YES", "COMPRESS=LZW", "BIGTIFF=IF_SAFER"]
    )
    if out is None:
        raise RuntimeError(f"地形の複雑さラスターを作成できません: {output_path}")

    out.SetGeoTransform(ref.GetGeoTransform())
    out.SetProjection(ref.GetProjection())
    band = out.GetRasterBand(1)
    band.SetNoDataValue(_NODATA)

    result = np.full(arr.shape, _NODATA, dtype=np.float32)
    good = valid & np.isfinite(arr)
    result[good] = arr[good].astype(np.float32)

    band.WriteArray(result)
    band.FlushCache()
    out.FlushCache()
    out = None
    ref = None

    check = gdal.Open(output_path, gdal.GA_ReadOnly)
    if check is None:
        raise RuntimeError(f"地形の複雑さラスターを再度開けません: {output_path}")
    stats = check.GetRasterBand(1).GetStatistics(False, True)
    check = None
    if stats is None or not all(np.isfinite(float(v)) for v in stats[:3]):
        raise RuntimeError(f"地形の複雑さラスターの統計値が不正です: {stats}")

    return output_path


def generate(dem_filepath: str, output_dir: str) -> str:
    """
    林野庁MORIZON「地形の複雑さ（SHC）」QGIS 3.44安定版。

    元プラグインの処理仕様を維持:
      1. Gaussian平滑化: MODE=1（円形）, RADIUS=12, SIGMA=3
      2. SAGA METHOD=6相当 Zevenbergen & Thorne Plan Curvature
      3. 曲率の標準偏差を小数4桁に丸め、±3σを外れ値として除外
      4. shc_param（初期値49）の円形近傍で標準偏差を計算
      5. MORIZON解析DEMと同一グリッドで Y_11_chikei.tif を出力

    QGIS 3.44で不安定な SAGA provider / QgsRasterCalculator /
    grass7:r.neighbors への依存を外し、GDAL + NumPyで実装する。
    """
    os.makedirs(output_dir, exist_ok=True)

    ds, dem, dem_valid = _read_dem(dem_filepath)
    gt = ds.GetGeoTransform()
    cell_x = abs(float(gt[1]))
    cell_y = abs(float(gt[5]))
    if not np.isfinite(cell_x) or not np.isfinite(cell_y) or cell_x <= 0 or cell_y <= 0:
        ds = None
        raise RuntimeError("解析DEMのピクセルサイズを取得できません。")
    if abs(cell_x - cell_y) > max(cell_x, cell_y) * 1.0e-6:
        ds = None
        raise RuntimeError(
            f"SHC計算には正方形セルが必要です。X={cell_x}, Y={cell_y}"
        )

    # 1) DEM Gaussian smoothing
    smoothed, smooth_valid = _gaussian_smooth(
        dem, dem_valid, sigma=3.0, radius=12
    )

    # 2) Plan curvature (SAGA METHOD=6)
    curvature, curvature_valid = _plan_curvature_zevenbergen(
        smoothed, smooth_valid, cell_x
    )

    # 3) ±3σ outlier removal; original plugin rounds stddev to 4 decimals first.
    vals = curvature[curvature_valid]
    if vals.size == 0:
        ds = None
        raise RuntimeError("平面曲率の有効セルがありません。")

    curvature_stddev = round(float(np.std(vals)), 4)
    if not np.isfinite(curvature_stddev):
        ds = None
        raise RuntimeError("平面曲率の標準偏差を計算できません。")

    normalized_valid = (
        curvature_valid &
        (curvature >= -3.0 * curvature_stddev) &
        (curvature <=  3.0 * curvature_stddev)
    )

    # 4) Circular neighborhood STD
    size = int(float(SettingsManager().get_setting("shc_param")))
    shc, shc_valid = _circular_std(curvature, normalized_valid, size)

    # Final NoData follows the original DEM coverage.
    shc_valid &= dem_valid

    output_path = os.path.join(
        output_dir, OUTPUT_SHC["FILE_NAME"] + ".tif"
    )
    ds = None
    return _write_like(dem_filepath, output_path, shc, shc_valid)
