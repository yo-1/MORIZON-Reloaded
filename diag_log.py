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
import logging
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

# dev9: UI停止がMORIZONの操作に関係するかどうかの判定に使う状態。
# diag_logはUIクラス（ダイアログ）に依存させたくないため、具体的な可視判定は
# register_dialog_visibility_check() で外部（forest_zoning.py）から1回だけ
# 登録してもらう。未登録の間は「ダイアログは開いていない」として扱う。
_dialog_visible_check = None
# 実行ボタン押下〜処理完了の区間中かどうか（ネストに備えてカウンタにする）。
_processing_active_count = 0


def _is_ui_thread() -> bool:
    return threading.current_thread() is threading.main_thread()


def register_dialog_visibility_check(check):
    """MORIZONのメインダイアログが表示中かどうかを調べる呼び出し可能オブジェクトを登録する。

    UiStallWatchdogが、MORIZONの計測区間と重ならない停止をInfoにするか
    Warningのままにするかの判定に使う（dev9）。
    """
    global _dialog_visible_check
    _dialog_visible_check = check


def _is_dialog_visible() -> bool:
    if _dialog_visible_check is None:
        return False
    try:
        return bool(_dialog_visible_check())
    except Exception:
        return False


@contextmanager
def processing_active():
    """MORIZONの処理スレッド実行中（実行ボタン押下〜完了）であることを示す区間。

    この区間中にUI停止を検知した場合、計測区間と重ならなくても利用者への
    影響があるためWarningのまま扱う（dev9）。
    """
    global _processing_active_count
    _processing_active_count += 1
    try:
        yield
    finally:
        _processing_active_count -= 1


def _is_morizon_operation_active() -> bool:
    return _is_dialog_visible() or _processing_active_count > 0


def log(message: str, level=Qgis.Info):
    try:
        QgsMessageLog.logMessage(
            f"[{time.strftime('%H:%M:%S')}] {message}", LOG_TAG, level)
    except Exception:
        logging.getLogger("MORIZON").warning(
            "QGIS log unavailable: %s", message, exc_info=True)


def log_exception(context: str, error: Exception) -> None:
    """記録可能な例外を残し、呼び出し元の継続動作は変えない。"""
    log(f"{context}: {type(error).__name__}: {error}")


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
        # dev9: MORIZONの計測区間と重ならず、ダイアログも閉じている・処理中
        # でもない（＝MORIZONが関与していないと判断した）停止の累計。
        self._info_stall_count = 0
        self._info_stall_total_seconds = 0.0

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
        except Exception as exc:
            log_exception("stop", exc)
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
            log(f"UIスレッドが約{stalled:.1f}秒応答していませんでした。"
                f"重なった計測区間: {', '.join(overlapping[-5:])}", Qgis.Warning)
            return

        if _is_morizon_operation_active():
            # 計測区間とは重ならないが、ダイアログが開いている、または
            # 実行ボタン押下〜完了の処理中（dev9）。利用者への影響が
            # あり得るため、従来どおりWarningのまま扱う。
            if _recent_spans:
                # 直近に完了した区間名を参考情報として併記する。因果関係の
                # 証拠ではないが、「MORIZON側の既知の処理は何も動いていな
                # かった」ことを示す手がかりになる。
                label, start, end = _recent_spans[-1]
                detail = (f"未計測の処理（直近の完了区間: {label}、"
                          f"停止開始の{last - end:.1f}秒前に完了）")
            else:
                detail = "未計測の処理（計測区間の記録なし）"
            log(f"UIスレッドが約{stalled:.1f}秒応答していませんでした。"
                f"重なった計測区間: {detail}", Qgis.Warning)
            return

        # dev9: 計測区間と重ならず、ダイアログも閉じている・処理中でもない
        # 停止。MORIZONの不具合ではなく、QGIS本体や他プラグインによる停止
        # である可能性が高いため、Warningではなく参考情報(Info)として出す
        # （他プラグインを長時間実行している間、MORIZONタブにWarningが
        # 大量に出て不具合に見えていた問題への対処）。
        self._info_stall_count += 1
        self._info_stall_total_seconds += stalled
        log(f"QGISのUIスレッドが約{stalled:.1f}秒応答していませんでした"
            f"（MORIZONの処理とは重なっていません。QGIS本体・他プラグイン等の"
            f"可能性があります）", Qgis.Info)
        log(f"参考: 起動後、MORIZON外要因と判定したUI停止は累計"
            f"{self._info_stall_count}件、合計{self._info_stall_total_seconds:.1f}秒です。",
            Qgis.Info)
