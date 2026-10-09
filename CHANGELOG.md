# Changelog

All notable changes to MORIZON Reloaded are documented here.

## 2.3.0-rc3-dev15 — 2026-10-09 (test build, not yet released)

While diffing the ported code against the original pre-port MORIZON v2.1
source file-by-file (a numeric-fidelity review requested by the user),
`processes/raster_writer/shc.py`'s rewrite of SAGA's
`slopeaspectcurvature` (METHOD=6, Zevenbergen & Thorne 1987) carried a
comment claiming that doubling the `r`/`t` second-derivative coefficients
was needed to match "legacy SAGA 2.x" behavior. No QGIS/SAGA is available
in this environment, so this was checked by installing real SAGA 9.3.1,
GDAL 3.8.4, and GRASS 8.3.2 via apt and running the actual algorithms
against a synthetic DEM.

### Fixed

- (O-24) Removed the `r *= 2.0; t *= 2.0` doubling in
  `_plan_curvature_zevenbergen()`. Comparing against real SAGA 9.3.1's
  `C_PLAN` output: the doubled (shipped) formula had correlation 0.990
  with SAGA's actual output and was systematically too large by a
  non-constant factor (median ratio ~1.7x — not a clean linear scaling,
  confirming a formula error rather than a version-specific constant).
  With the doubling removed, the formula matches SAGA's real output to
  floating-point precision (correlation 1.000000, max diff 1.07e-08).
  SAGA's own source (`Morphometry.cpp`, `Set_Zevenbergen` /
  `Set_From_Polynom`) was also read directly and contains no such
  doubling. The other two re-implemented SHC steps — the circular
  Gaussian smoothing and the circular-neighborhood standard deviation —
  were independently verified (against a from-scratch brute-force 2D
  convolution, and against a real GRASS `r.neighbors` run) and already
  matched exactly; only this one line was wrong.
- This changes SHC (地形の複雑さ) output values, which had been
  systematically overestimated, and therefore the downstream 災害リスク
  score and final zoning class for affected cells. See
  `docs/OPEN_ISSUES.md` (O-24) for the full verification data and
  methodology. Not yet exercised on the Windows/QGIS/SAGA on-device
  environment — real on-device SHC output should be re-checked against
  this build before release.

## 2.3.0-rc3-dev14 — 2026-10-08 (test build, not yet released)

O-15's remaining unresolved item: a multi-second UI stall recorded right
after plugin load, reproduced 7+ times across independent sessions and
QGIS profiles, while the existing `プラグイン初期化: __init__` /
`initGui` timed spans both consistently measure 0.0s. The contradiction
pointed at work happening outside what those spans cover.

### Added (diagnostic only, no behavior change)

- `forest_zoning.py`'s top-level import of `forest_zoning_main_dialog`
  (which transitively imports every tab controller, `processes/`, and
  `utils/__init__.py` — the latter has a module-level `import processing`,
  which can trigger QGIS's Processing provider initialization the first
  time anything in the session touches it) now runs inside `timed()`, so
  its actual duration is logged directly instead of being invisible.
  `diag_log`'s own import was moved earlier to make this possible; it
  only depends on `qgis.core`/`qgis.PyQt.QtCore`, so this reordering is
  safe.
- No analysis formulas, thresholds, NoData rules, CRS treatment, or
  output names were changed. Not yet exercised on-device.

## 2.3.0-rc3-dev13 — 2026-10-08 (test build, not yet released)

Found while manually testing dev8's threshold-init dedup (delete a scoring
output's layer group, recalculate just that element, return to the scoring
tab): the affected combobox ended up pointing at an unrelated layer
(収益性/地位（カラマツ）instead of 収益性/集材作業効率), with its threshold
spinboxes still showing stale values left over from before. Reproduced
identically twice on-device. Clicking "レイヤーを自動設定" fixed it both
times, but that button also force-resets every scoring threshold to its
computed default, even for elements the recalculation never touched —
automating that call on every element-calculation finish would have
silently wiped manually-tuned thresholds the user never asked to change.

### Fixed

- Element calculation's finish handling (`add_elements_layer_to_project`)
  now calls a new, narrower check
  (`ForestZoningMainDialogScoring.fix_broken_scoring_layer_bindings`)
  instead. It inspects each of the 6 scoring-tab comboboxes, and only
  touches the ones whose current layer's source file no longer matches
  what that slot expects (by the same strict filename/generation
  matching `レイヤーを自動設定` uses, scoped to layers already loaded in
  the project since element calculation just added them). A mismatched
  combobox is re-bound and has its threshold recomputed; everything
  else — including other parameters' manually-edited thresholds — is
  left completely untouched.
- No analysis formulas, thresholds, NoData rules, CRS treatment, or
  output names were changed; this only corrects which layer the scoring
  UI reads from before the user runs scoring.
- The underlying mis-binding and the "レイヤーを自動設定" workaround were
  confirmed on-device (2026-10-08, two independent reproductions); this
  automatic fix itself has not yet been verified on-device.

## 2.3.0-rc3-dev12 — 2026-10-08 (test build, not yet released)

Found from a full dev11 on-device log (not just the excerpts reviewed
earlier): the original dev6 bug report that motivated dev8's dedup fix
named `災害リスク/保全対象を含む流域` as the repeatedly-reinitialized layer,
but dev8's dedup (`ScoringObject.last_init_layer_id`, scoped to the 5
threshold-adjustable scoring elements) never actually covers `savearea` —
it isn't one of those 5. The exact symptom dev8 was meant to close was
still reproducing, confirmed identically in two independent on-device runs
in the same session (7 repeated calls each time, right after element
calculation finishes).

### Fixed

- `utils.get_initial_thresholds()` — the shared, expensive (full raster
  scan) function both the scoring tab's and zoning tab's threshold
  initialization call into — now caches its result per
  `(layer id, classes_count)` for the life of the QGIS session. This
  closes the gap regardless of which combobox or code path re-queries the
  same layer, including the `savearea` case dev8's combobox-scoped dedup
  could not reach. No change to the computed values themselves (a cache
  hit returns the same thresholds a fresh computation would). Harmless on
  the sample data (0.0–0.1s per call) but may matter on large rasters.
  **Confirmed on-device (2026-10-08, TestFlight profile)**: the repeated
  calls for 保全対象を含む流域 dropped from 7 in a row to 2 real
  computations + 1 cache hit (a new `しきい値初期値のキャッシュ再利用` log line
  appeared, proving the skip actually happened). It didn't reach exactly
  1 computation because two different `classes_count` values (3 and 2)
  were both observed for this layer in the same run — each gets its own
  cache entry by design, and the root cause of why both values touch this
  one layer is still unconfirmed. No UI-stall warning occurred during the
  actual element-calculation run (O-15/O-17 regression clear).
- No analysis formulas, thresholds, NoData rules, CRS treatment, output
  names, or dev8's existing same-combobox dedup were changed.

## 2.3.0-rc3-dev11 — 2026-10-08 (test build, not yet released)

Found during the same dev10 on-device test session that confirmed the O-18
fix. Two unrelated issues surfaced: a stale version label (urgent, user
flagged it directly), and a new failure one step past where O-18 used to
block (diagnostic logging added, root cause not yet confirmed).

### Fixed

- `branding.py`'s `BUILD_LABEL` (the version shown in the MORIZON dialog's
  own header, distinct from the QGIS Plugin Manager's version column) was
  hardcoded to `v2.3.0-rc3-dev5` and never updated across dev6 through
  dev10 — five releases where the in-dialog label silently drifted from
  the real installed version. It now reads the version from `metadata.txt`
  at import time (same `configparser` pattern already used by
  `scripts/static_check.py` and `scripts/build_plugin_zip.py`), so this
  class of bug cannot recur.

### Added (diagnostic only, no behavior change)

- `get_quantile_renderer()` (`processes/raster_styler/utils.py`) now logs
  the computed Min/Max and the resulting color-ramp shader item count for
  every raster it styles, plus a warning when Min equals Max (a constant
  raster, which Quantile classification may not be able to split into
  multiple classes).

### Confirmed on-device (dev10 build, same test session)

- **O-18 fix confirmed working**: re-running element calculation no
  longer fails with "Deleting ... failed: Permission denied" for
  集材作業効率. The GDAL write now succeeds (falling back to a
  versioned path when needed).
- **New failure found one step later** (O-19, not yet understood): right
  after the successful write, `write_scoring_qml()` failed with
  "QML内に連続値カラーランプ（colorrampshader/item）が見つかりません。
  QGIS 3.44のQML構造またはレイヤ描画方式が旧版と異なります。" This step
  was never reached in any earlier test, because O-18's Permission Denied
  failure always aborted the element calculation before getting here.
  Whether this is specific to 集材作業効率's data (e.g., a constant-value
  raster on the small sample DEM) or a broader QGIS 3.44 `createShader()`
  behavior change is not yet confirmed; see docs/OPEN_ISSUES.md O-19.

## 2.3.0-rc3-dev10 — 2026-10-08 (test build, not yet released)

Found during dev9 on-device testing: re-running element calculation while
the previous run's 集材作業効率 (cost) output was still loaded in QGIS
always failed. Reproduced 3 times in the same session.

### Fixed

- `processes/raster_writer/cost.py`'s `_write_like()` called `gdal.Create()`
  directly on the existing output path, with no fallback for a locked file
  — unlike `siteidx.py`, `distance.py`, `savearea.py`, `shc.py`, and
  `zoning.py`, which already use `resolve_writable_output_path()` (O-09) to
  fall back to a versioned `_v2`, `_v3`, ... path when the existing file
  can't be deleted. `cost.py` now uses the same helper, matching the other
  writers exactly. `generate()` and `_generate_ruggedness()` now propagate
  the (possibly versioned) resolved path back to their callers instead of
  always returning the original unversioned path.
- This bug had a cascading effect on-device: because 集材作業効率 kept
  failing, its stale (earlier-run) output stayed in the project and got
  auto-selected by the scoring tab, causing `profit.py`'s grid-mismatch
  check to fail scoring ("収益性の入力3ラスターのグリッドが一致していません").
  No code change was needed for `profit.py` itself — its validation was
  working correctly on bad input.

No analysis formulas, thresholds, NoData rules, CRS treatment, or output
names were changed; this only adds the same lock-fallback every other
element writer already has.

### Verified

- `py_compile` and `scripts/static_check.py` pass.
- **Not yet re-tested on-device** — the on-device session that found this
  bug was the one being fixed; the fix itself has not been exercised on
  real hardware yet.

## 2.3.0-rc3-dev9 — 2026-10-02 (test build, not yet released)

Requested by claude.ai (relayed via the user) after a ~39-hour run of
another QGIS plugin (CS立体図) produced 12 `UIスレッドが約N秒応答していませんでした`
warnings in the `MORIZON` log tab — 6 of them 3677-39478s each, totaling
~132275s (~94% of the run) — while MORIZON itself was never operated.
The watchdog was detecting correctly; the problem was that these
MORIZON-unrelated stalls appeared as `Warning` in the MORIZON tab,
making them look like a MORIZON bug. See `docs/OPEN_ISSUES.md` (O-17)
for the full report and analysis.

### Changed

- `UiStallWatchdog.check()` now logs a stall as `Qgis.Info` instead of
  `Qgis.Warning` when **both** of the following hold: (1) the stall
  doesn't overlap any MORIZON `timed()` span, and (2) the MORIZON main
  dialog is closed and no MORIZON processing thread (element calc /
  scoring / zoning / aggregation) is running. The Info line reads
  "QGISのUIスレッドが約N秒応答していませんでした（MORIZONの処理とは重なっ
  ていません。QGIS本体・他プラグイン等の可能性があります）", followed by a
  cumulative count + total-seconds line.
- A stall that overlaps a MORIZON span, or occurs while the dialog is
  open or a MORIZON thread is running (even without an overlapping
  span), stays `Qgis.Warning` exactly as before — user-facing MORIZON
  stalls are not silenced.
- "Dialog open" is read live from `ForestZoning.is_visible_main_dialog()`
  via a callback `diag_log.py` holds (`register_dialog_visibility_check()`,
  registered once in `initGui()`), avoiding a duplicated/stale flag.
  "Processing active" is a counter (`processing_active()` context
  manager) wrapped around the existing `thread.start(); progress_dialog.exec_()`
  pattern in all four `run_*()` methods (elements/scoring/zoning/aggregate).

### Not changed

- Analysis formulas, thresholds, NoData rules, CRS treatment, output
  names.
- The watchdog's detection method itself (250ms `QTimer`, 2.0s
  threshold) — only how a detected stall is classified and logged.
- dev8's changes (`8a0b074`, `03c0991`, `e082d5e`), kept in a separate
  commit per the request.
- The dev8-C startup timing spans (`プラグイン初期化: __init__` /
  `initGui`) are kept; a startup-time stall before the dialog opens
  will now log as Info (unless it overlaps one of those spans), which
  is intentional — the O-15 pre-launch-stall investigation is unrelated
  to this change and still uses those spans when present.

### Verification

- `py_compile` and `scripts/static_check.py` pass.
- A pure-Python stub test (fake `qgis.core`/`qgis.PyQt.QtCore` modules,
  not real QGIS) exercises `UiStallWatchdog.check()`'s four branch
  combinations (overlap / no-overlap+idle / no-overlap+dialog-open /
  no-overlap+processing) and the cumulative Info counter. **Not yet
  tested on-device.**

## 2.3.0-rc3-dev8 — 2026-10-01 (test build, not yet released)

Requested by claude.ai (relayed via the user) following the dev6 on-device
results. Both changes below are **not yet verified on-device** — `py_compile`
and `static_check.py` only. See `docs/OPEN_ISSUES.md` (O-15 dev8 section)
for the full analysis, including an explicitly flagged behavior-change risk
that needs on-device confirmation.

### Fixed

- `init_scoring_rlayer_stats()` (the scoring-tab threshold Quantile
  initializer) no longer re-runs `bandStatistics()` (a full-raster scan) for
  a layer it has already initialized. On dev6, the element-calculation
  finish step called it ~50-60 times for the same layer (0.0s each on the
  sample raster; a plausible hang cause on a large one). Callers that must
  always re-initialize (initial dialog construction, and
  `set_scoring_layer_combobox`'s bulk reflect after auto-detecting layers)
  now pass `force=True`. Skips are counted via `count_event()`.
  **Needs on-device check**: this also means a layer re-selection that
  re-fires `layerChanged` for the same already-selected layer (the
  duplicate-call symptom above) will no longer silently reset a
  hand-edited threshold back to the Quantile default for that redundant
  fire — intended, but unverified in practice.

### Added (diagnostic only, no behavior change)

- `ForestZoning.__init__` and `initGui()` are now wrapped in `timed()`
  spans, to help determine whether a startup-time UI-thread stall (two
  on-device sessions recorded 7.0s/77.6s and 11.9s/56.7s pairs right after
  plugin load, before the MORIZON dialog was ever opened, unrelated to the
  `QgsProject.instance()` fix) happens inside MORIZON's own startup code.
- `UiStallWatchdog` now reports the most recently completed `timed()` span
  (and how long before the stall it finished) when no span overlaps the
  stall window, instead of a bare "未計測の処理". Not proof of causation,
  but evidence either way when MORIZON's own spans are fast.

## 2.3.0-rc3-dev7 — 2026-09-30 (test build, not yet released)

On-device test (Windows / QGIS 3.44, sample data `Zoningkit_SAMPLE`) of
dev6 confirmed the O-15 UI-thread stall is resolved: zero
`UIスレッドが約N秒応答していませんでした` warnings occurred during the
element/scoring/zoning/aggregation workflow (previously 26.6s in dev5).
See `docs/TEST_RECORD.md` and `docs/OPEN_ISSUES.md` (O-15) for the full
log analysis. A separate, unconfirmed 7.0s/77.6s stall was still recorded
right after plugin load, before the MORIZON dialog was ever opened; no
MORIZON `timed()` span overlapped it, so it is likely unrelated to the
`QgsProject.instance()` fix. Cause not yet identified.

### Fixed

- Aggregation no longer falsely warns about an "unexpected count column"
  (`count_NODA`) when the output is a Shapefile. The DBF field-name limit
  (10 characters) truncates `count_NODATA` to `count_NODA`; the diagnostic
  check now accepts both spellings as the normal NoData-count column.
  Diagnostic log only — no analysis formulas, thresholds, NoData rules,
  CRS treatment, or output names were changed; `ratio_1`..`ratio_4` only
  ever read `count_1`..`count_4` and were unaffected either way.

## 2.3.0-rc3-dev6 — 2026-09-30 (test build, not yet released)

On-device test (Windows / QGIS 3.44, sample data) recorded the dev5 UI-stall
watchdog firing: `UIスレッドが約26.6秒応答していませんでした`, overlapping five
consecutive `要素計算: UI更新(refresh_elements_ui)` calls (3.1-3.3s each).
Root cause found via a Python-console measurement: `QgsProject().instance()`
(with parentheses) constructs a new QgsProject object on every call, and
`refresh_elements_ui` invoked this path roughly 16 times per UI refresh
through its validation calls (~2s per refresh). Measured: 16 calls via
`QgsProject().instance()` = 2.095s vs. 16 calls via `QgsProject.instance()`
= 0.0147s (~140x). This build has not yet been re-tested on-device; the
patch itself was verified only with `py_compile` and `static_check.py`.
No analysis formulas, thresholds, NoData rules, CRS treatment, or output
names were changed.

### Fixed

- Replaced `QgsProject().instance()` with `QgsProject.instance()` in four
  places (`forest_zoning_main_dialog_elements.py` x2,
  `forest_zoning_main_dialog_scoring.py` x1,
  `forest_zoning_main_dialog_aggregate.py` x1).
- `refresh_elements_ui` now calls `get_elements_error_texts()` once and
  reuses the result for both the error label and the run-button state,
  instead of calling it twice.

### Known follow-ups (not in this build)

- `refresh_elements_ui` still fires 4-9 times per single user action
  (no event debouncing yet).
- Threshold-initialisation appears to run ~60 duplicate calls for the same
  layer (disaster-risk / conservation-basin) when the element step
  finishes; harmless on the small sample raster but a likely stall cause
  on large rasters.
- The `count_NODATA` diagnostic-log false warning may still occur if the
  aggregation output truncates column names to 10 characters.
- `refresh_elements_ui` duration grows within a single burst (2.1s to
  3.2s); cause not yet identified.

## 2.3.0-rc3-dev5 — 2026-09-29 (test build, not yet released)

Diagnostic build. On the sample data every stage finishes, but the log
showed 18-23 s gaps between opening the scoring/zoning tabs and the start of
processing, during which the QGIS window seemed to stop responding. The gaps
contained no log lines, so dev5 adds instrumentation to locate them.
No analysis formulas, thresholds, NoData rules, CRS treatment, or output
names were changed.

### Added

- UIスレッドの停止検知（`UiStallWatchdog`）。2秒以上応答しなかった場合、停止秒数と、その時間帯に重なった計測区間を `MORIZON` タブへ警告として出力。
- 各ダイアログの実行ボタン押下から処理スレッド開始までの区間を記録（要素計算・スコアリング・ゾーニング・集計）。
- `onLayersChanged`（レイヤーツリー変更のたびに3画面のUI更新が走る）の発火回数と、遅かった場合の所要時間を記録。
- UI更新・入力レイヤー自動設定・しきい値設定・ラスター統計取得(`bandStatistics`)を、0.3秒以上かかった場合のみ記録。

### Fixed

- 集計時、`native:zonalhistogram` が常に出力する `count_NODATA` 列を「想定外のcount列」と誤って警告していたのを修正（診断ログの誤検知のみで、集計結果には影響しない）。

## 2.3.0-rc3-dev4 — 2026-09-29 (test build, not yet released)

Diagnostic build. dev3 showed that all six element calculations finish on the
sample data, so the remaining "stops/freezes" report is not reproduced by the
element step. dev4 extends the log to the stages dev3 did not cover.
No analysis formulas, thresholds, NoData rules, CRS treatment, or output
names were changed.

### Added

- 各要素の完了行 `DONE: <工程> (秒)` を追加（dev3は開始行のみで、所要時間は次の行から逆算する必要があった）。
- スコアリング（収益性・災害リスク）、ゾーニング、集計の各工程について、開始・完了・失敗と所要秒数を `MORIZON` タブへ出力。失敗時はトレースバックも出力。
- ダイアログ表示時にUIスレッドで実行される「しきい値初期値の算出（Quantile分類）」と、その内部の `bandStatistics`（全ピクセル走査）の所要秒数を出力。大きなラスターでQGISが応答しなくなる原因の切り分け用。
- 集計時、`native:zonalhistogram` の出力列（`count_*`）を記録し、`count_1`〜`count_4` が不足する場合と想定外の列がある場合に警告を出力。
- ゾーニング出力ラスターのデータ型・サイズを記録（集計時の「入力ラスタは浮動小数点型」警告の確認用）。

### Documentation

- CHANGELOG冒頭の説明文が dev2/dev1 の間に紛れていたため、先頭へ移動。
- README に、動作に影響しない既知のログメッセージの一覧を追加。

## 2.3.0-rc3-dev3 — 2026-09-29 (test build, not yet released)

Diagnostic build for the "freezes when running the sample data" report.
The cause has not been identified yet; this build only makes the stopping
step visible and removes one known GRASS provider-ID dependency.
No analysis formulas, thresholds, NoData rules, CRS treatment, or output
names were changed.

### Added

- 各要素・保全流域の主要工程（GRASS呼び出し前後、polygonize、重複判定、rasterize、最終書き出し）の開始/完了を、QGISの「ログメッセージ」パネル（タブ名 `MORIZON`）へ時刻付きで出力。処理が止まって見えた場合、最後の行が停止工程の手がかりになる。
- 要素計算が失敗した場合、例外のトレースバックを同ログへ出力。

### Fixed

- 集材作業効率（起伏量方式）が `grass7:r.neighbors` 固定だったため、GRASS ProviderのIDが `grass` の環境で失敗し得た。`grass:r.neighbors` → `grass7:r.neighbors` の順に試すよう変更（`savearea.py` と同方式）。

## 2.3.0-rc3-dev2 — 2026-09-17 (test build, not yet released)

### Fixed

- ツールバーに同一アイコンの「起動」と「設定」が2個表示されていたため、ツールバーには「起動」のみを表示し、「設定」はプラグインメニュー内に残すよう修正。
- プラグイン無効化・再有効化時にカスタムツールバーが残らないよう、ツールバーからアクションを除去したうえでツールバー自体を削除するよう修正。
- `dataChanged`シグナルの解除箇所が誤って再接続になっていた不具合を修正。
- メイン画面のビルドラベルを実際の試験版番号に同期。

## 2.3.0-rc3-dev1 — 2026-09-17 (test build, not yet released)

Stabilization fixes made during the Claude Code handoff, built for Windows
on-device testing (see docs/VALIDATION.md ST01-ST08 and docs/TEST_RECORD.md in the
source repository; these files are not included in the distribution ZIP).
Whether this becomes the official rc3, or is folded into it after further
changes, will be decided once test results are in. No analysis formulas,
thresholds, NoData rules, CRS treatment, or output names were changed.

- Fixed a silent import failure in `processes/__init__.py`: submodule
  import errors occurring after a successful QGIS API import were only
  printed and swallowed, later surfacing as an unrelated `AttributeError`
  when `processes.raster_writer` etc. were referenced. Now logged via
  `QgsMessageLog` and re-raised, so a real dependency problem fails
  clearly at plugin load time instead.
- Unified the Windows file-lock fallback across all writers. `siteidx.py`
  (site index) and `distance.py` (road distance) previously aborted the
  whole run when an existing output file was locked (e.g. still open in
  QGIS), while `savearea`/`shc`/`risk`/`profit`/`zoning` already fell back
  to versioned `_v2`, `_v3`, ... files. Both now use the same fallback via
  the new `resolve_writable_output_path()` helper.
- Added a preflight check for the GRASS Processing Provider before running
  the conservation-basin element, with concrete recovery guidance, instead
  of failing only after other elements had already been computed.
- Added a preflight CRS-mismatch warning for the road-distance element
  (DEM vs. road network), shown before computation starts; the existing
  in-process CRS check remains as a safety net.
- Added a preflight resolution/CRS diagnostic for the site-index element
  (DEM vs. NPP/SRAD/VTEX); the automatic grid alignment during processing
  is unchanged, this only surfaces the difference beforehand.

## 2.3.0-rc2 — 2026-09-03

- Fixed print-layout creation on QGIS 3.44 by passing
  `Qgis.ScaleBarSegmentSizeMode.FitWidth` instead of the legacy integer value.
- Corrected displayed line breaks in the missing-CRS confirmation dialog.
- Clarified that the aggregation output destination is a result file.
- No analysis formulas, thresholds, scoring, or zoning logic were changed.

## 2.3.0-rc1 — 2026-09-02

First public release candidate for clean-environment testing. This is not the
final v2.3.0 release.

### Compatibility

- Updated the plugin for QGIS 3.44.x and QGIS-provided PyQt.
- Reimplemented unavailable legacy Processing, SAGA, GRASS, temporary-raster,
  and raster-calculator paths with current QGIS Native, GRASS, GDAL, and NumPy
  components where required.
- Preserved the original MORIZON analysis logic, parameters, score structure,
  and four-quadrant zoning method.

### Processing stability

- Stabilized site-index generation and NoData handling.
- Stabilized logging-system efficiency processing.
- Reimplemented road-distance processing on the analysis DEM grid.
- Reproduced the legacy terrain-complexity calculation for current QGIS.
- Updated conservation-basin overlap processing and CRS handling.
- Updated profitability, disaster-risk, zoning, and aggregation output handling.
- Added Windows file-lock fallbacks using versioned output names.

### User interface

- Added automatic input and output layer binding.
- Added recent-dataset and path-handling improvements.
- Updated scoring, zoning, color, grouping, and aggregation behavior for QGIS
  3.44.
- Added the MORIZON Reloaded name, icon, and interface branding.

### Distribution

- Added GPL v3 license text, README, NOTICE, and this changelog.
- Added original-project and Reloaded-modification notices to Python sources.
- Removed internal STEP development notes from the public package.
- Limited deletion of existing Shapefile outputs to known sidecar extensions.

## 2.1 — Original MORIZON

- Original Forestry Agency MORIZON package used as the compatibility-port base.
