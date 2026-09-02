# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

import os
import tempfile

from osgeo import gdal
import numpy as np
import processing

from ...settings_manager import SettingsManager
from ..costcsv_parser import CostcsvParser
from ...constants import OUTPUT_COST
from . import shc


def _read_band(path):
    ds = gdal.Open(path, gdal.GA_ReadOnly)
    if ds is None:
        raise RuntimeError(f"ラスターを開けません: {path}")
    band = ds.GetRasterBand(1)
    arr = band.ReadAsArray().astype(np.float64, copy=False)
    nd = band.GetNoDataValue()
    gt = ds.GetGeoTransform()
    prj = ds.GetProjection()
    return ds, band, arr, nd, gt, prj


def _write_like(reference_path, output_path, array, nodata=-9999, dtype=gdal.GDT_Float32):
    ref = gdal.Open(reference_path, gdal.GA_ReadOnly)
    if ref is None:
        raise RuntimeError(f"基準ラスターを開けません: {reference_path}")
    drv = gdal.GetDriverByName("GTiff")
    out = drv.Create(output_path, ref.RasterXSize, ref.RasterYSize, 1, dtype,
                     options=["TILED=YES", "COMPRESS=LZW", "BIGTIFF=IF_SAFER"])
    if out is None:
        raise RuntimeError(f"出力ラスターを作成できません: {output_path}")
    out.SetGeoTransform(ref.GetGeoTransform())
    out.SetProjection(ref.GetProjection())
    b = out.GetRasterBand(1)
    b.SetNoDataValue(nodata)
    b.WriteArray(array)
    b.FlushCache()
    out.FlushCache()
    out = None
    ref = None
    return output_path


def generate(dem_filepath: str, costcsv_filepath: str, output_dir: str) -> str:
    """林野庁版の作業システム判定を維持しつつ、最終判定をGDAL/NumPyで安定計算する。"""
    os.makedirs(output_dir, exist_ok=True)
    work_dir = os.path.join(output_dir, "_morizon_work")
    os.makedirs(work_dir, exist_ok=True)

    if SettingsManager().get_setting("cost_algorithm") == "ruggedness":
        element_filepath = _generate_ruggedness(
            dem_filepath, os.path.join(work_dir, "cost_ruggedness.tif"))
    else:
        shc_dir = os.path.join(work_dir, "cost_shc")
        os.makedirs(shc_dir, exist_ok=True)
        element_filepath = shc.generate(dem_filepath, shc_dir)

    slope_filepath = os.path.join(work_dir, "cost_slope.tif")
    processing.run("native:slope", {
        "INPUT": dem_filepath,
        "Z_FACTOR": 1.0,
        "OUTPUT": slope_filepath
    })
    if not os.path.exists(slope_filepath):
        raise RuntimeError(f"傾斜ラスターを作成できません: {slope_filepath}")

    dem_ds, dem_band, dem, dem_nd, _, _ = _read_band(dem_filepath)
    ele_ds, ele_band, ele, ele_nd, _, _ = _read_band(element_filepath)
    slp_ds, slp_band, slp, slp_nd, _, _ = _read_band(slope_filepath)

    if dem.shape != ele.shape or dem.shape != slp.shape:
        raise RuntimeError(
            f"作業システム計算ラスターのサイズが一致しません: DEM={dem.shape}, element={ele.shape}, slope={slp.shape}")

    valid = np.isfinite(dem) & np.isfinite(ele) & np.isfinite(slp)
    if dem_nd is not None:
        valid &= dem != dem_nd
    if ele_nd is not None:
        valid &= ele != ele_nd
    if slp_nd is not None:
        valid &= slp != slp_nd

    parser = CostcsvParser(costcsv_filepath)
    result = np.zeros(dem.shape, dtype=np.float32)

    # 元MORIZONの条件: lower <= value < upper。表の欄外は0。
    for r0, r1, s0, s1, score in parser._get_score_tuples():
        try:
            r0, r1 = float(str(r0).replace("\ufeff", "").strip()), float(str(r1).replace("\ufeff", "").strip())
            s0, s1 = float(str(s0).replace("\ufeff", "").strip()), float(str(s1).replace("\ufeff", "").strip())
            score = float(str(score).replace("\ufeff", "").strip())
        except ValueError as e:
            raise RuntimeError(
                "作業システムCSVに数値として解釈できない値があります: "
                f"起伏量=({r0},{r1}), 傾斜=({s0},{s1}), コード={score}"
            ) from e
        mask = valid & (ele >= r0) & (ele < r1) & (slp >= s0) & (slp < s1)
        result[mask] = score

    nodata = -9999.0
    result[~valid] = nodata
    output_filepath = os.path.join(output_dir, OUTPUT_COST["FILE_NAME"] + ".tif")
    _write_like(dem_filepath, output_filepath, result, nodata, gdal.GDT_Float32)

    dem_ds = ele_ds = slp_ds = None
    return output_filepath


def _generate_ruggedness(dem_filepath: str, output_filepath: str) -> str:
    """起伏量=max-min。GRASS近傍処理は維持し、差分のみGDAL/NumPyで計算する。"""
    size = int(float(SettingsManager().get_setting("ruggedness_param")))
    work_dir = os.path.dirname(output_filepath)
    os.makedirs(work_dir, exist_ok=True)
    min_filepath = os.path.join(work_dir, "ruggedness_min.tif")
    max_filepath = os.path.join(work_dir, "ruggedness_max.tif")

    common = {
        "-a": False, "-c": False,
        "GRASS_RASTER_FORMAT_META": "", "GRASS_RASTER_FORMAT_OPT": "",
        "GRASS_REGION_CELLSIZE_PARAMETER": 0,
        "GRASS_REGION_PARAMETER": None,
        "gauss": None, "input": dem_filepath,
        "quantile": "", "selection": None,
        "size": size, "weight": "",
    }
    p = dict(common); p.update({"method": 3, "output": min_filepath})
    processing.run("grass7:r.neighbors", p)
    p = dict(common); p.update({"method": 4, "output": max_filepath})
    processing.run("grass7:r.neighbors", p)

    if not os.path.exists(min_filepath) or not os.path.exists(max_filepath):
        raise RuntimeError("起伏量計算用の最小値/最大値ラスターを作成できません")

    min_ds, min_band, mn, min_nd, _, _ = _read_band(min_filepath)
    max_ds, max_band, mx, max_nd, _, _ = _read_band(max_filepath)
    dem_ds, dem_band, dem, dem_nd, _, _ = _read_band(dem_filepath)
    if mn.shape != mx.shape or mn.shape != dem.shape:
        raise RuntimeError(f"起伏量計算ラスターのサイズが一致しません: min={mn.shape}, max={mx.shape}, dem={dem.shape}")

    valid = np.isfinite(mn) & np.isfinite(mx) & np.isfinite(dem)
    if min_nd is not None: valid &= mn != min_nd
    if max_nd is not None: valid &= mx != max_nd
    if dem_nd is not None: valid &= dem != dem_nd

    nodata = -9999.0
    rugged = np.full(dem.shape, nodata, dtype=np.float32)
    rugged[valid] = (mx[valid] - mn[valid]).astype(np.float32)
    _write_like(dem_filepath, output_filepath, rugged, nodata, gdal.GDT_Float32)
    min_ds = max_ds = dem_ds = None
    return output_filepath
