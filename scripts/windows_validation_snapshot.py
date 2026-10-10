"""Collect QGIS 3.44 Windows validation evidence from an output directory.

Run this file in the QGIS Python console after the workflow has completed.
Set MORIZON_VALIDATION_OUTPUT and MORIZON_VALIDATION_REFERENCE to skip dialogs.
"""

from __future__ import annotations

import configparser
import hashlib
import importlib
import json
import os
import platform
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from osgeo import gdal, ogr
from qgis.PyQt.QtWidgets import QFileDialog
from qgis.core import Qgis, QgsApplication, QgsProject


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def raster_details(path: Path) -> dict:
    dataset = gdal.Open(str(path), gdal.GA_ReadOnly)
    if dataset is None:
        raise ValueError(f"GeoTIFFを開けません: {path}")
    details = {
        "width": dataset.RasterXSize,
        "height": dataset.RasterYSize,
        "geotransform": list(dataset.GetGeoTransform()),
        "projection_wkt": dataset.GetProjectionRef(),
        "bands": [],
    }
    for index in range(1, dataset.RasterCount + 1):
        band = dataset.GetRasterBand(index)
        nodata = band.GetNoDataValue()
        digest = hashlib.sha256()
        minimum, maximum = None, None
        valid_count, nodata_count = 0, 0
        for y in range(0, dataset.RasterYSize, 256):
            height = min(256, dataset.RasterYSize - y)
            pixels = np.asarray(band.ReadAsArray(0, y, dataset.RasterXSize, height))
            digest.update(pixels.tobytes(order="C"))
            valid = np.isfinite(pixels)
            if nodata is not None:
                valid &= ~np.isnan(pixels) if np.isnan(nodata) else pixels != nodata
            nodata_count += int(valid.size - np.count_nonzero(valid))
            valid_count += int(np.count_nonzero(valid))
            if np.any(valid):
                block_min = float(np.min(pixels[valid]))
                block_max = float(np.max(pixels[valid]))
                minimum = block_min if minimum is None else min(minimum, block_min)
                maximum = block_max if maximum is None else max(maximum, block_max)
        details["bands"].append({
            "index": index,
            "data_type": gdal.GetDataTypeName(band.DataType),
            "nodata": nodata,
            "valid_pixels": valid_count,
            "nodata_pixels": nodata_count,
            "minimum": minimum,
            "maximum": maximum,
            "pixel_sha256": digest.hexdigest(),
        })
    dataset = None
    return details


def vector_details(path: Path) -> dict:
    dataset = ogr.Open(str(path), 0)
    if dataset is None:
        raise ValueError(f"Shapefileを開けません: {path}")
    layer = dataset.GetLayer(0)
    fields = [layer.GetLayerDefn().GetFieldDefn(i).GetName()
              for i in range(layer.GetLayerDefn().GetFieldCount())]
    details = {"features": layer.GetFeatureCount(), "fields": fields}
    dataset = None
    return details


def collect(root: Path) -> dict:
    rasters = {}
    vectors = {}
    settings = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if "DATA" in path.relative_to(root).parts:
            continue
        if path.suffix.lower() in {".tif", ".tiff"}:
            rasters[relative] = raster_details(path)
        elif path.suffix.lower() == ".shp":
            vectors[relative] = vector_details(path)
        elif path.name in {"params.json", "thresholds.json"}:
            settings[relative] = {"sha256": sha256_file(path)}
    return {"rasters": rasters, "vectors": vectors, "settings": settings}


def compare(current: dict, reference: dict) -> dict:
    results = {}
    reference_rasters = reference["rasters"]
    for name, raster in current["rasters"].items():
        match = name if name in reference_rasters else None
        if match is None:
            candidates = [other for other in reference_rasters if Path(other).name == Path(name).name]
            if len(candidates) == 1:
                match = candidates[0]
        if match is None:
            results[name] = {"reference": None, "pixel_equal": None}
            continue
        old = reference_rasters[match]
        results[name] = {
            "reference": match,
            "grid_equal": (
                raster["width"] == old["width"]
                and raster["height"] == old["height"]
                and raster["geotransform"] == old["geotransform"]
                and raster["projection_wkt"] == old["projection_wkt"]
            ),
            "pixel_equal": (
                len(raster["bands"]) == len(old["bands"])
                and all(a["pixel_sha256"] == b["pixel_sha256"]
                        for a, b in zip(raster["bands"], old["bands"]))
            ),
        }
    return results


def main() -> Path:
    output = os.environ.get("MORIZON_VALIDATION_OUTPUT")
    if not output:
        output = QFileDialog.getExistingDirectory(None, "MORIZONの新しい出力フォルダを選択")
    if not output:
        raise ValueError("出力フォルダが選択されていません")
    root = Path(output)
    if not root.is_dir():
        raise ValueError(f"出力フォルダがありません: {root}")

    reference_path = os.environ.get("MORIZON_VALIDATION_REFERENCE")
    if reference_path is None:
        reference_path = QFileDialog.getExistingDirectory(
            None, "以前の採用済み出力フォルダ（無ければキャンセル）"
        )
    reference_root = Path(reference_path) if reference_path and reference_path != "skip" else None

    plugin_version = None
    try:
        metadata_path = Path(importlib.import_module("MORIZON").__file__).with_name("metadata.txt")
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(metadata_path, encoding="utf-8")
        plugin_version = parser["general"].get("version")
    except (ImportError, KeyError, OSError):
        pass

    provider = (QgsApplication.processingRegistry().providerById("grass")
                or QgsApplication.processingRegistry().providerById("grass7"))
    current = collect(root)
    if not current["rasters"] and not current["vectors"]:
        raise ValueError("GeoTIFFまたはShapefileの出力が見つかりません")
    report = {
        "recorded_at": datetime.now().astimezone().isoformat(),
        "environment": {
            "qgis": Qgis.QGIS_VERSION,
            "gdal": gdal.VersionInfo("--version"),
            "python": sys.version,
            "windows": platform.platform(),
            "grass_provider": provider.name() if provider else None,
            "plugin_version": plugin_version,
            "project_crs": QgsProject.instance().crs().authid(),
        },
        "outputs": current,
        "reference_root_provided": reference_root is not None,
    }
    if reference_root is not None:
        if not reference_root.is_dir():
            raise ValueError(f"基準出力フォルダがありません: {reference_root}")
        report["raster_comparison"] = compare(current, collect(reference_root))
    destination = root / "MORIZON_validation_snapshot.json"
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"MORIZON検証結果: {destination}")
    print(f"GeoTIFF {len(current['rasters'])}件、Shapefile {len(current['vectors'])}件")
    return destination


if __name__ == "__main__":
    main()
