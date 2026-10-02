# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

import os

import processing

from ...utils import (
    get_tiff_info
)


def resolve_writable_output_path(output_path: str) -> str:
    """既存出力ファイルがWindowsでロックされていても処理を止めないための共通ヘルパー。

    出力先が存在しない、または削除できればそのまま同じパスを返す。
    QGIS/GDALがGeoTIFFを開いたままなどの理由で削除できない場合は、
    ``<name>_v2.<ext>``, ``_v3.<ext>`` ... のように空いている世代付き
    パスへ退避する。原版仕様（計算式・NoData・グリッド）には影響しない、
    純粋な出力先の決定のみを行う。

    全writerで世代付けの規則（``_vN``サフィックス、番号の振り方）を統一
    することが目的。スコアリング側のレイヤ自動選択は、この規則に従って
    最新世代を検出する（``forest_zoning_main_dialog_scoring.py``）。
    """
    if not os.path.exists(output_path):
        return output_path
    try:
        os.remove(output_path)
        return output_path
    except (PermissionError, OSError):
        stem, ext = os.path.splitext(output_path)
        generation = 2
        while True:
            candidate = f"{stem}_v{generation}{ext}"
            if not os.path.exists(candidate):
                return candidate
            try:
                os.remove(candidate)
                return candidate
            except (PermissionError, OSError):
                generation += 1
                if generation > 999:
                    raise RuntimeError(
                        f"出力先を確保できません（世代上限超過）: {output_path}"
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
