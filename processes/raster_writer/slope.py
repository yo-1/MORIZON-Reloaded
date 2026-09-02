# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

import os

import processing

from ...constants import OUTPUT_SLOPE


def generate(dem_filepath: str, output_dir: str) -> str:
    """
    DEMから傾斜ラスターを生成する
    """
    output_filepath = os.path.join(
        output_dir, OUTPUT_SLOPE['FILE_NAME'] + ".tif")
    processing.run("native:slope", {
        "INPUT": dem_filepath,
        "Z_FACTOR": 1.0,
        "OUTPUT": output_filepath
    })
    return output_filepath
