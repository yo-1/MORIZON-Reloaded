#!/usr/bin/env python3
"""Real-QGIS regression test for vector CRS preflight (savearea / distance).

Guards against the 2026-08-27 ZoningKit_09 failure mode: a building
shapefile converted from Fundamental Geospatial Data GML kept lat/lon
coordinates and lost its .prj, was overlapped against plane-rectangular
basins, selected 0 basins, and the all-zero conservation layer was
written silently (the run predates the rc2 zero-selection guard).

Run with the QGIS Python of a 3.44 environment, e.g.:
    python3 scripts/test_vector_crs_preflight.py
Exits non-zero on the first failed expectation.
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    from qgis.core import QgsApplication

    prefix = os.environ.get("CONDA_PREFIX") or "/usr"
    QgsApplication.setPrefixPath(prefix, True)
    app = QgsApplication([], False)
    app.initQgis()
    sys.path.append(os.path.join(prefix, "share", "qgis", "python", "plugins"))
    try:
        from processing.core.Processing import Processing

        Processing.initialize()
    except Exception:
        pass

    import importlib
    import types

    package = types.ModuleType("MORIZON")
    package.__path__ = [str(ROOT)]
    sys.modules["MORIZON"] = package
    savearea = importlib.import_module(
        "MORIZON.processes.raster_writer.savearea"
    )
    distance = importlib.import_module(
        "MORIZON.processes.raster_writer.distance"
    )

    from osgeo import gdal, ogr, osr
    from qgis.core import QgsProcessingException

    gdal.UseExceptions()
    tmp = Path(tempfile.mkdtemp(prefix="morizon-crs-test-"))

    # --- synthetic DEM: 200x200 cells, 10 m, EPSG:6677, realistic extent ---
    dem_path = str(tmp / "dem.tif")
    drv = gdal.GetDriverByName("GTiff")
    ds = drv.Create(dem_path, 200, 200, 1, gdal.GDT_Float32)
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(6677)
    ds.SetProjection(srs.ExportToWkt())
    ds.SetGeoTransform((-100000, 10, 0, 100000, 0, -10))
    import numpy as np

    yy, xx = np.mgrid[0:200, 0:200]
    ds.GetRasterBand(1).WriteArray((xx + yy).astype("float32"))
    ds = None

    # lon/lat of the DEM centre (1000 m, 1000 m in EPSG:6677)
    src = osr.SpatialReference(); src.ImportFromEPSG(6677)
    dst = osr.SpatialReference(); dst.ImportFromEPSG(6668)
    src.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    dst.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    ct = osr.CoordinateTransformation(src, dst)
    clon, clat, _ = ct.TransformPoint(-99000, 99000)

    def write_shp(path, srs_epsg, ring):
        drv2 = ogr.GetDriverByName("ESRI Shapefile")
        ds2 = drv2.CreateDataSource(str(path))
        s = None
        if srs_epsg:
            s = osr.SpatialReference()
            s.ImportFromEPSG(srs_epsg)
        layer = ds2.CreateLayer("x", s, ogr.wkbPolygon)
        geom_ring = ogr.Geometry(ogr.wkbLinearRing)
        for x, y in ring:
            geom_ring.AddPoint(x, y)
        poly = ogr.Geometry(ogr.wkbPolygon)
        poly.AddGeometry(geom_ring)
        feat = ogr.Feature(layer.GetLayerDefn())
        feat.SetGeometry(poly)
        layer.CreateFeature(feat)
        ds2 = None

    deg_ring = [
        (clon - 0.001, clat - 0.001), (clon + 0.001, clat - 0.001),
        (clon + 0.001, clat + 0.001), (clon - 0.001, clat + 0.001),
        (clon - 0.001, clat - 0.001),
    ]
    b_nocrs = tmp / "b_nocrs.shp"
    write_shp(b_nocrs, None, deg_ring)
    b_wrong = tmp / "b_wrong.shp"
    write_shp(b_wrong, 6677, deg_ring)  # prj says 6677, coords are degrees

    failures = []

    def expect_raise(label, fn, needle):
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            if needle in str(e):
                print(f"PASS {label}: raised as expected ({needle})")
            else:
                failures.append(f"{label}: wrong error: {e}")
                print(f"FAIL {label}: wrong error: {e}")
            return
        failures.append(f"{label}: no error raised")
        print(f"FAIL {label}: no error raised")

    # 1) savearea.generate must fail fast on CRS-less buildings,
    #    before any GRASS watershed work starts.
    expect_raise(
        "savearea generate CRS-less",
        lambda: savearea.generate(dem_path, str(b_nocrs), str(tmp / "o1"), None),
        "CRSが不明",
    )
    # 2) preflight passes when the 6668 override is supplied.
    try:
        savearea._preflight_building_check(str(b_nocrs), "EPSG:6668", dem_path)
        print("PASS savearea preflight with EPSG:6668 override")
    except Exception as e:  # noqa: BLE001
        failures.append(f"preflight override: {e}")
        print(f"FAIL savearea preflight with override: {e}")
    # 3) valid-but-wrong CRS (prj=6677, degree coords) -> extent guard.
    expect_raise(
        "savearea preflight extent guard",
        lambda: savearea._preflight_building_check(str(b_wrong), None, dem_path),
        "重なっていません",
    )

    # 4) distance.generate must stop on CRS-less road data.
    r_nocrs = tmp / "r_nocrs.shp"
    drv2 = ogr.GetDriverByName("ESRI Shapefile")
    ds2 = drv2.CreateDataSource(str(r_nocrs))
    layer = ds2.CreateLayer("x", None, ogr.wkbLineString)
    line = ogr.Geometry(ogr.wkbLineString)
    line.AddPoint(-99900, 99900); line.AddPoint(-98100, 98100)
    feat = ogr.Feature(layer.GetLayerDefn())
    feat.SetGeometry(line)
    layer.CreateFeature(feat)
    ds2 = None
    expect_raise(
        "distance generate CRS-less road",
        lambda: distance.generate(dem_path, str(r_nocrs), str(tmp / "o2")),
        "座標参照系（CRS）が不明",
    )

    if failures:
        print("FAILURES:", len(failures))
        sys.exit(1)
    print("ALL PREFLIGHT TESTS PASSED")


if __name__ == "__main__":
    main()
