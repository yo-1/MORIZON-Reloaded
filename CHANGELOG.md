# Changelog

All notable changes to MORIZON Reloaded are documented here.

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
