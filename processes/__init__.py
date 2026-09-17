# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

try:
    # unittest時にQGIS-APIが読めなくてエラーになるのを避ける
    from qgis.PyQt.QtCore import *
    from qgis.PyQt.QtGui import *
    from qgis.PyQt.QtWidgets import *
    from qgis.core import *
    from qgis.gui import *
except Exception as e:
    # QGIS APIが読み込めない環境（例: pure-Python単体テスト、静的チェック）。
    # このパッケージはQGIS専用処理のため、ここで打ち切ってよい。
    print(e)
else:
    import os

    try:
        from . import aggregate
        from . import elements
        from . import scoring
        from . import zoning
        from . import raster_writer
        from . import raster_styler
        from . import printlayout
        from ..constants import OUTPUT_AGGREGATE, ZONING_COLORS
    except Exception as e:
        # QGIS自体は読み込めたのに、ここで失敗するのは依存ライブラリの
        # バージョン不整合など「本来のQGIS実行環境での設定不備」である
        # 可能性が高い。ここで握りつぶすと、後段で processes.raster_writer
        # 等への参照が AttributeError となり原因不明のエラーに化ける。
        # QGISログパネルに残したうえで再送出し、プラグイン読込エラーとして
        # 明確に失敗させる。
        QgsMessageLog.logMessage(
            f"MORIZON: processesサブモジュールの読込に失敗しました: {e}",
            "MORIZON",
            Qgis.Critical,
        )
        raise



