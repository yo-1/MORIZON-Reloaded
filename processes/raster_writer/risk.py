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

from ...constants import OUTPUT_RISK


def generate(slope_rlayer,
             slope_thresholds,
             shc_rlayer,
             shc_thresholds,
             savearea_rlayer,
             output_dir):
    """
    林野庁原版の災害リスクスコアリングをQGIS 3.44向けに安定実装。

    原版ルール:
      傾斜・地形の複雑さは3区分。
      保全対象を含む流域だけは 0=>score1, 1=>score2。
      3要素の点数を加算。
    """
    slope_ds = _open_layer(slope_rlayer, "傾斜")
    shc_ds = _open_layer(shc_rlayer, "地形の複雑さ")
    save_ds = _open_layer(savearea_rlayer, "保全対象を含む流域")

    sig = _grid_signature(slope_ds)
    if _grid_signature(shc_ds) != sig or _grid_signature(save_ds) != sig:
        raise RuntimeError(
            "災害リスクの入力3ラスターのグリッドが一致していません。"
            "要素計算結果を同一10m解析グリッドで作成してください。"
        )

    slope_b = slope_ds.GetRasterBand(1)
    shc_b = shc_ds.GetRasterBand(1)
    save_b = save_ds.GetRasterBand(1)
    slope = slope_b.ReadAsArray().astype(np.float64, copy=False)
    shc = shc_b.ReadAsArray().astype(np.float64, copy=False)
    save = save_b.ReadAsArray().astype(np.float64, copy=False)

    valid = (
        _valid_mask(slope, slope_b.GetNoDataValue())
        & _valid_mask(shc, shc_b.GetNoDataValue())
        & _valid_mask(save, save_b.GetNoDataValue())
    )

    settings = SettingsManager().get_settings()
    save_scores = settings["scores_savearea"]
    save_score = np.zeros(save.shape, dtype=np.float32)
    save_score[save == 0] = float(save_scores[0])
    save_score[save == 1] = float(save_scores[1])

    # 原版ではsaveareaは0/1のみを想定。その他の値は有効値にしない。
    valid &= ((save == 0) | (save == 1))

    result = (
        _score_three(slope, slope_thresholds, settings["scores_slope"])
        + _score_three(shc, shc_thresholds, settings["scores_shc"])
        + save_score
    )

    output_filepath = os.path.join(
        output_dir, OUTPUT_RISK["FILE_NAME"] + ".tif"
    )
    target = _publish_atomic(slope_ds, result, valid, output_filepath)
    slope_ds = shc_ds = save_ds = None
    return target
