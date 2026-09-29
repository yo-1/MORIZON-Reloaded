# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

"""調査用ログの共通ヘルパー。

QGISの「ログメッセージ」パネル（タブ名: MORIZON）へ時刻付きで出力する。
QgsMessageLogはスレッドセーフなので、処理スレッド・UIスレッドのどちらからも使える。
ログ出力の失敗で本処理を止めないこと（例外は握りつぶす）を設計上の前提とする。
"""

import time
from contextlib import contextmanager

from qgis.core import Qgis, QgsMessageLog

LOG_TAG = "MORIZON"


def log(message: str, level=Qgis.Info):
    try:
        QgsMessageLog.logMessage(
            f"[{time.strftime('%H:%M:%S')}] {message}", LOG_TAG, level)
    except Exception:
        pass


@contextmanager
def timed(label: str):
    """工程の開始・完了・失敗と所要秒数を記録する。例外は必ず再送出する。

    失敗時は短い1行だけを残す。トレースバックは、例外を最終的に捕捉する側
    （各ProcessingThreadのexcept節）で1回だけ出力する。
    """
    started = time.monotonic()
    log(f"{label} 開始")
    try:
        yield
    except Exception as e:
        log(f"{label} 失敗 ({time.monotonic() - started:.1f}s): "
            f"{type(e).__name__}: {e}", Qgis.Warning)
        raise
    else:
        log(f"{label} 完了 ({time.monotonic() - started:.1f}s)")
