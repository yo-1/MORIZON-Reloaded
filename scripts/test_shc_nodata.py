"""Numerical regression for SHC Plan A without QGIS/GDAL imports."""
import ast
import math
from pathlib import Path
import unittest

import numpy as np


SOURCE = Path(__file__).resolve().parents[1] / "processes/raster_writer/shc.py"


def load_numerical_functions(source):
    tree = ast.parse(source)
    names = {
        "_conv_axis_same", "_gaussian_smooth", "_plan_curvature_zevenbergen",
        "_horizontal_sum", "_circular_std",
    }
    tree.body = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    namespace = {"np": np, "math": math}
    exec(compile(tree, str(SOURCE), "exec"), namespace)
    return namespace


def pipeline(functions, dem, valid):
    smooth, smooth_valid = functions["_gaussian_smooth"](dem, valid)
    curvature, curvature_valid = functions["_plan_curvature_zevenbergen"](
        smooth, smooth_valid, 10.0
    )
    sigma = round(float(np.std(curvature[curvature_valid])), 4)
    normalized = (
        curvature_valid
        & (curvature >= -3.0 * sigma)
        & (curvature <= 3.0 * sigma)
    )
    shc, shc_valid = functions["_circular_std"](curvature, normalized, 49)
    shc_valid &= valid
    return smooth, smooth_valid, curvature_valid, shc, shc_valid


class PlanANoDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = SOURCE.read_text(encoding="utf-8")
        patched = "good = (denominator > 1.0e-12) & valid"
        if source.count(patched) != 1:
            raise AssertionError("Plan A validity condition must occur once")
        cls.current = load_numerical_functions(source)
        cls.baseline = load_numerical_functions(
            source.replace(patched, "good = denominator > 1.0e-12")
        )

    def test_complete_dem_is_bit_identical(self):
        y, x = np.mgrid[:81, :81]
        hill = 100.0 + 30.0 * np.exp(-((x - 40) ** 2 + (y - 40) ** 2) / 200)
        for dem in (hill, np.full((81, 81), 100.0), np.full((81, 81), -0.44)):
            with self.subTest(mean=float(dem.mean())):
                valid = np.ones(dem.shape, dtype=bool)
                old = pipeline(self.baseline, dem, valid)
                new = pipeline(self.current, dem, valid)
                for left, right in zip(old, new):
                    self.assertEqual(left.dtype, right.dtype)
                    self.assertEqual(left.tobytes(), right.tobytes())

    def test_internal_and_edge_holes_do_not_generate_curvature(self):
        y, x = np.mgrid[:81, :81]
        dem = 100.0 + np.sin(x / 9) + np.cos(y / 11)
        for location in ("internal", "edge"):
            with self.subTest(location=location):
                valid = np.ones(dem.shape, dtype=bool)
                if location == "internal":
                    valid[35:45, 35:45] = False
                else:
                    valid[:6, :] = False
                input_dem = np.where(valid, dem, -9999.0)
                old = pipeline(self.baseline, input_dem, valid)
                new = pipeline(self.current, input_dem, valid)
                self.assertTrue(np.any(old[1] & ~valid))
                self.assertFalse(np.any(new[1] & ~valid))
                self.assertTrue(np.isnan(new[0][~valid]).all())
                self.assertFalse(np.any(new[2] & ~valid))
                self.assertFalse(np.any(new[4] & ~valid))
                self.assertTrue(np.any(new[4]))
                self.assertTrue(np.isfinite(new[3][new[4]]).all())

    def test_all_nodata_has_no_smoothed_values(self):
        valid = np.zeros((81, 81), dtype=bool)
        smooth, good = self.current["_gaussian_smooth"](
            np.full(valid.shape, -9999.0), valid
        )
        self.assertFalse(good.any())
        self.assertTrue(np.isnan(smooth).all())


if __name__ == "__main__":
    unittest.main()
