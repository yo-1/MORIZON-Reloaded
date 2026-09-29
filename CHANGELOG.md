# Changelog

All notable changes to MORIZON Reloaded are documented here.

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
