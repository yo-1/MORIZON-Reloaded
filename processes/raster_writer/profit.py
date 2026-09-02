# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only


import os
import uuid
import numpy as np
from osgeo import gdal

from ...settings_manager import SettingsManager

gdal.UseExceptions()
NODATA_VALUE = -9999.0


def _layer_source(layer):
    return layer.dataProvider().dataSourceUri().split("|", 1)[0]


def _open_layer(layer, label):
    path = _layer_source(layer)
    ds = gdal.Open(path, gdal.GA_ReadOnly)
    if ds is None:
        raise RuntimeError(f"{label}ラスターを開けません: {path}")
    return ds


def _grid_signature(ds):
    return (
        ds.RasterXSize,
        ds.RasterYSize,
        tuple(float(v) for v in ds.GetGeoTransform()),
        ds.GetProjection(),
    )


def _valid_mask(arr, nodata):
    valid = np.isfinite(arr)
    if nodata is not None:
        if np.isnan(float(nodata)):
            valid &= ~np.isnan(arr)
        else:
            valid &= ~np.isclose(arr, float(nodata), rtol=0.0, atol=1.0e-12)
    return valid


def _score_three(arr, thresholds, scores):
    t1, t2 = float(thresholds[0]), float(thresholds[1])
    if t1 > t2:
        raise RuntimeError(f"スコアしきい値が逆転しています: {t1} > {t2}")
    out = np.zeros(arr.shape, dtype=np.float32)
    out[arr <= t1] = float(scores[0])
    out[(arr > t1) & (arr <= t2)] = float(scores[1])
    out[arr > t2] = float(scores[2])
    return out


def _publish_atomic(reference_ds, arr, valid, output_filepath):
    """
    直接本番TIFFを書かず、一時TIFFへ完全出力後に公開する。
    既存本番ファイルがWindowsでロックされている場合は _vN へ退避。
    """
    output_dir = os.path.dirname(output_filepath)
    os.makedirs(output_dir, exist_ok=True)
    work_dir = os.path.join(output_dir, "_MORIZON_work")
    os.makedirs(work_dir, exist_ok=True)

    temp_path = os.path.join(
        work_dir, f"scoring_{uuid.uuid4().hex}.tif"
    )
    drv = gdal.GetDriverByName("GTiff")
    dst = drv.Create(
        temp_path,
        reference_ds.RasterXSize,
        reference_ds.RasterYSize,
        1,
        gdal.GDT_Float32,
        options=["COMPRESS=LZW", "TILED=YES", "BIGTIFF=IF_SAFER"],
    )
    if dst is None:
        raise RuntimeError(f"スコアリング一時ラスターを作成できません: {temp_path}")
    dst.SetGeoTransform(reference_ds.GetGeoTransform())
    dst.SetProjection(reference_ds.GetProjection())
    band = dst.GetRasterBand(1)
    band.SetNoDataValue(NODATA_VALUE)

    final = np.full(arr.shape, NODATA_VALUE, dtype=np.float32)
    final[valid] = arr[valid].astype(np.float32)
    band.WriteArray(final)
    band.FlushCache()
    dst.FlushCache()
    band = None
    dst = None

    def next_versioned(path):
        stem, ext = os.path.splitext(path)
        i = 2
        while os.path.exists(f"{stem}_v{i}{ext}"):
            i += 1
        return f"{stem}_v{i}{ext}"

    target = output_filepath
    if os.path.exists(target):
        try:
            os.remove(target)
        except OSError:
            target = next_versioned(output_filepath)

    try:
        os.replace(temp_path, target)
    except OSError:
        target = next_versioned(output_filepath)
        os.replace(temp_path, target)

    return target

from ...constants import OUTPUT_PROFIT


def generate(siteidx_rlayer,
             siteidx_thresholds,
             cost_rlayer,
             cost_thresholds,
             distance_rlayer,
             distance_thresholds,
             output_dir):
    """
    林野庁原版の収益性スコアリングをQGIS 3.44向けに安定実装。

    原版ルール:
      地位・集材作業効率・地利をそれぞれ3区分へ点数化し、その3要素を加算。
      score1: value <= threshold1
      score2: threshold1 < value <= threshold2
      score3: threshold2 < value
    """
    site_ds = _open_layer(siteidx_rlayer, "地位")
    cost_ds = _open_layer(cost_rlayer, "集材作業効率")
    dist_ds = _open_layer(distance_rlayer, "地利")

    sig = _grid_signature(site_ds)
    if _grid_signature(cost_ds) != sig or _grid_signature(dist_ds) != sig:
        raise RuntimeError(
            "収益性の入力3ラスターのグリッドが一致していません。"
            "要素計算結果を同一10m解析グリッドで作成してください。"
        )

    site_b = site_ds.GetRasterBand(1)
    cost_b = cost_ds.GetRasterBand(1)
    dist_b = dist_ds.GetRasterBand(1)
    site = site_b.ReadAsArray().astype(np.float64, copy=False)
    cost = cost_b.ReadAsArray().astype(np.float64, copy=False)
    dist = dist_b.ReadAsArray().astype(np.float64, copy=False)

    valid = (
        _valid_mask(site, site_b.GetNoDataValue())
        & _valid_mask(cost, cost_b.GetNoDataValue())
        & _valid_mask(dist, dist_b.GetNoDataValue())
    )

    settings = SettingsManager().get_settings()
    result = (
        _score_three(site, siteidx_thresholds, settings["scores_siteidx"])
        + _score_three(cost, cost_thresholds, settings["scores_cost"])
        + _score_three(dist, distance_thresholds, settings["scores_distance"])
    )

    output_filepath = os.path.join(
        output_dir, OUTPUT_PROFIT["FILE_NAME"] + ".tif"
    )
    target = _publish_atomic(site_ds, result, valid, output_filepath)
    site_ds = cost_ds = dist_ds = None
    return target
