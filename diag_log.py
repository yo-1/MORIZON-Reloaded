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

import functools
import threading
import time
from collections import deque
from contextlib import contextmanager

from qgis.core import Qgis, QgsMessageLog
from qgis.PyQt.QtCore import QTimer

LOG_TAG = "MORIZON"

# UIスレッド上で完了した計測区間の直近履歴 (label, start, end)。
# UI停止を検知したとき、停止時間帯に重なる区間を表示して原因箇所を推定するために使う。
# 処理スレッド側の区間はUI停止と無関係なので記録しない。
_recent_spans = deque(maxlen=300)
_event_counts = {}


def _is_ui_thread() -> bool:
    return threading.current_thread() is threading.main_thread()


def log(message: str, level=Qgis.Info):
    try:
        QgsMessageLog.logMessage(
            f"[{time.strftime('%H:%M:%S')}] {message}", LOG_TAG, level)
    except Exception:
        pass


@contextmanager
def timed(label: str, min_seconds=None):
    """工程の開始・完了・失敗と所要秒数を記録する。例外は必ず再送出する。

    失敗時は短い1行だけを残す。トレースバックは、例外を最終的に捕捉する側
    （各ProcessingThreadのexcept節）で1回だけ出力する。

    min_seconds を指定すると「開始」行は出さず、所要時間がその秒数以上だった
    場合だけ完了行を出す。UIイベントから頻繁に呼ばれる処理で、ログが溢れない
    ようにするための指定（例外時は常に記録する）。
    """
    started = time.monotonic()
    if min_seconds is None:
        log(f"{label} 開始")
    try:
        yield
    except Exception as e:
        log(f"{label} 失敗 ({time.monotonic() - started:.1f}s): "
            f"{type(e).__name__}: {e}", Qgis.Warning)
        raise
    else:
        elapsed = time.monotonic() - started
        if min_seconds is None:
            log(f"{label} 完了 ({elapsed:.1f}s)")
        elif elapsed >= min_seconds:
            log(f"{label} 完了 ({elapsed:.1f}s) ※{min_seconds}秒以上かかりました")
    finally:
        if _is_ui_thread():
            _recent_spans.append((label, started, time.monotonic()))


def log_if_slow(label: str, min_seconds: float = 0.3):
    """引数なしのメソッド用デコレータ。遅かった場合だけ所要時間を記録する。

    Qtのシグナルに直接接続されるスロットへ付けても、PyQtが渡す余分な引数で
    TypeErrorにならないよう、wrapperの引数は self のみにしている。
    引数を取るメソッドには使わないこと。
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self):
            with timed(label, min_seconds=min_seconds):
                return func(self)
        return wrapper
    return decorator


def count_event(name: str, every: int = 50):
    """頻繁に発火するイベントの回数を数え、every回ごとに累計を記録する。"""
    n = _event_counts.get(name, 0) + 1
    _event_counts[name] = n
    if n == 1 or n % every == 0:
        log(f"イベント発火回数: {name} 累計{n}回")


class UiStallWatchdog:
    """UIスレッドの停止（イベントループの詰まり）を検知して記録する。

    メインスレッドのQTimerを一定間隔で動かし、次の発火までの間隔が想定より
    大きく延びていれば、その間UIスレッドがブロックされていたと判断する。
    ブロック中は検知できず、ブロックが解けた直後に事後的に記録される。
    停止時間帯に重なる計測区間があれば併記する（無ければ「未計測」）。
    """

    INTERVAL_MS = 250
    THRESHOLD_SECONDS = 2.0

    def __init__(self):
        self._timer = None
        self._last_tick = None

    def start(self):
        if self._timer is not None:
            return
        self._last_tick = time.monotonic()
        self._timer = QTimer()
        self._timer.setInterval(self.INTERVAL_MS)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()
        log(f"UI停止ウォッチドッグを開始しました（{self.THRESHOLD_SECONDS}秒以上の停止を記録）")

    def stop(self):
        if self._timer is None:
            return
        try:
            self._timer.stop()
            self._timer.timeout.disconnect(self._on_tick)
        except Exception:
            pass
        self._timer = None

    def _on_tick(self):
        self.check(time.monotonic())

    def check(self, now: float):
        """1回分の判定。テストしやすいよう時刻を引数に取る。"""
        last = self._last_tick
        self._last_tick = now
        if last is None:
            return
        stalled = now - last - self.INTERVAL_MS / 1000.0
        if stalled < self.THRESHOLD_SECONDS:
            return
        overlapping = [
            f"{label}({end - start:.1f}s)"
            for label, start, end in _recent_spans
            if end >= last and start <= now
        ]
        if overlapping:
            detail = ", ".join(overlapping[-5:])
        elif _recent_spans:
            # 重なった区間が無くても、直近に完了した区間名を参考情報として
            # 併記する。因果関係の証拠ではないが、「MORIZON側の既知の処理は
            # 何も動いていなかった（＝MORIZON外の要因の可能性が高い）」こと
            # を示す手がかりになる。
            label, start, end = _recent_spans[-1]
            detail = (f"未計測の処理（直近の完了区間: {label}、"
                      f"停止開始の{last - end:.1f}秒前に完了）")
        else:
            detail = "未計測の処理（計測区間の記録なし）"
        log(f"UIスレッドが約{stalled:.1f}秒応答していませんでした。"
            f"重なった計測区間: {detail}", Qgis.Warning)
