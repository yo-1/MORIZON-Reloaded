# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

import processing

from ...utils import (
    get_tiff_info
)


def resampling(tiff_filepath: str,
               target_resolution: int,
               output_filepath=None,
               resampling_alg_name="cubicspline") -> str:
    """
    TIFFを指定のZ解像度へリサンプリングする、EXTENTは変更されない
    """
    return processing.run("gdal:translate", {
        "EXTRA": f"-tr {target_resolution} {target_resolution} -r {resampling_alg_name}",
        "INPUT": tiff_filepath,
        "OUTPUT": output_filepath if output_filepath is not None else "TEMPORARY_OUTPUT"
    })["OUTPUT"]


def adjust_extent_and_resolution(basis_tiff_filepath: str,
                                 target_tiff_filepath: str,
                                 output_filepath=None,
                                 resampling_alg_name="cubicspline") -> str:
    """
    任意のラスターを、基準ラスターと同じ領域・解像度に調整して出力する
    """
    basis_deminfo = get_tiff_info(basis_tiff_filepath)
    resampling_alg_dict = {
        "nearest": 0,
        "bilinear": 1,
        "cubicspline": 3
    }
    resampling_alg = resampling_alg_dict.get(resampling_alg_name, 3)

    output = processing.run("gdal:warpreproject", {
        "TARGET_CRS": basis_deminfo["crs"],
        "TARGET_RESOLUTION": basis_deminfo["resolution"],
        "TARGET_EXTENT": f'{basis_deminfo["extent"][0]},{basis_deminfo["extent"][1]},{basis_deminfo["extent"][2]},{basis_deminfo["extent"][3]}',
        "TARGET_EXTENT_CRS": basis_deminfo["crs"],
        "RESAMPLING": resampling_alg,
        "INPUT": target_tiff_filepath,
        "OUTPUT": output_filepath if output_filepath is not None else "TEMPORARY_OUTPUT",
        "EXTRA": "-overwrite"
    })["OUTPUT"]
    return output
