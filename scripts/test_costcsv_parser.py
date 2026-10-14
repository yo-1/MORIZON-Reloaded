#!/usr/bin/env python3
"""QGIS-independent regression tests for malformed work-system CSV."""
import importlib.util
from pathlib import Path
import tempfile
import sys
sys.dont_write_bytecode = True
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("costcsv_parser", ROOT / "processes/costcsv_parser.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
Parser = module.CostcsvParser

class CsvTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "work.csv"
        self.text = (ROOT / "test_data/ZoningKit_SYNTH/DATA/SAGYO-SYSTEM_CSV/sagyou_SYNTH.csv").read_text(encoding="cp932")
    def parse(self, text, encoding="cp932"):
        self.path.write_bytes(text.encode(encoding))
        return Parser(str(self.path))
    def test_valid_cp932(self):
        parser = self.parse(self.text)
        self.assertEqual(len(parser._get_score_tuples()), 60)
        self.assertEqual(parser.get_score_names()[10], "CTL")
    def test_utf8_bom_matches_cp932(self):
        original = self.parse(self.text)
        utf8 = self.parse(self.text, "utf-8-sig")
        self.assertEqual(original.generate_expression_for_raster_calculator("R", "S"), utf8.generate_expression_for_raster_calculator("R", "S"))
        self.assertEqual(original.get_score_names(), utf8.get_score_names())
    def test_short_rows(self):
        with self.assertRaisesRegex(RuntimeError, "行数"):
            self.parse("\n".join(self.text.splitlines()[:10]))
    def test_semicolon_delimiter(self):
        with self.assertRaisesRegex(RuntimeError, "カンマ区切り"):
            self.parse(self.text.replace(",", ";"))
    def test_short_upper_row(self):
        rows = self.text.splitlines()
        rows[2] = ",".join(rows[2].split(",")[:3])
        with self.assertRaisesRegex(RuntimeError, "3行目"):
            self.parse("\n".join(rows))
    def test_missing_lower_name(self):
        rows = self.text.splitlines()
        rows[15] = "10"
        with self.assertRaisesRegex(RuntimeError, "16行目"):
            self.parse("\n".join(rows))

if __name__ == "__main__":
    unittest.main()
