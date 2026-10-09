# Changelog

All notable changes to MORIZON Reloaded are documented here.

The `2.3.0-rc3-dev1` through `2.3.0-rc3-dev18` entries below the `2.1`
entry are the internal diagnostic-build history that led up to the
`2.3.0` release (see "Development history" at the end of this file) —
none of those builds were released independently; `2.3.0` supersedes all
of them.

## 2.3.0 — 2026-10-09 (official release)

もりぞん（MORIZON）互換プラグインの最初の正式リリースです。QGIS 3.44.x
Solothurn向けに、原版（林野庁委託事業、日本森林技術協会がゾーニングの考え方
と作業フローを取りまとめ、MIERUNEが実装）の分析ロジック・しきい値・スコア
体系・四象限分類をそのまま維持しつつ、現行QGISで動作するよう再実装・安定化
したものです。`2.3.0-rc1`〜`2.3.0-rc3-dev18`の開発過程で見つかった修正点は
すべて本リリースに含まれています（詳細な経緯は本ファイル末尾の開発履歴、
および`docs/OPEN_ISSUES.md`参照）。

This is the first official release of the MORIZON compatibility port for
QGIS 3.44.x Solothurn. It preserves the original analysis logic,
thresholds, scoring structure, and four-quadrant zoning classification
unchanged, while re-implementing and stabilizing the plugin for current
QGIS. Every fix found during the `2.3.0-rc1` through `2.3.0-rc3-dev18`
diagnostic development series is included in this release (see
"Development history" below and `docs/OPEN_ISSUES.md` for the detailed,
per-issue record).

### Fixed

Numeric/processing-correctness fixes (affect output values):

- **地利 (road-distance) produced a sentinel value across the entire
  output** when the road network did not fully cover the DEM extent
  (e.g. a road layer clipped to a different area than the DEM). Distance
  is now computed on the union of the DEM and road-network extents,
  snapped to the DEM's own pixel grid, matching the original MORIZON's
  actual GRASS-based behavior. No change for the ordinary case where the
  road network is already inside the DEM extent. Verified against a real
  GRASS `r.grow.distance` run (max diff ~6.5e-05 m) and confirmed
  on-device.
- **地形の複雑さ (SHC / terrain-complexity) plan curvature was
  systematically overestimated** (~1.7x) due to an erroneous doubling of
  intermediate coefficients that did not match the real SAGA algorithm
  it ports. Removed; the corrected formula matches real SAGA 9.3.1
  output to floating-point precision (correlation 1.000000). This
  changes SHC output values and, downstream, the 災害リスク score and
  zoning class for affected cells. Confirmed on real hardware.
- Fixed a Windows file-lock bug in 集材作業効率 (cost) element
  calculation (`Permission denied` when a previous run's output was
  still open in QGIS); all element writers now share one versioned
  (`_v2`, `_v3`, ...) output-path fallback.
- Fixed the scoring tab losing track of which layer a combobox pointed
  to after a partial element recalculation (stale/mismatched layer
  binding); recalculating one element no longer disturbs the others'
  manually-tuned thresholds.
- Fixed the scoring tab's "統計値表示" (show statistics) dialog crashing
  with `RuntimeError: x must be a sequence` for every element, due to a
  matplotlib API incompatibility; confirmed working on-device for all
  five applicable elements.
- Fixed aggregation's zonal-histogram step from being called repeatedly
  (up to 7x) for the same layer on every element-calculation finish.

UI/stability fixes (no effect on analysis output):

- Fixed a ~20-second apparent UI freeze when opening the scoring/zoning
  tabs, caused by `QgsProject().instance()` constructing a new project
  object on every call instead of reusing the singleton.
- Long background-plugin UI stalls unrelated to MORIZON (e.g. another
  plugin running) no longer appear as misleading `Warning`-level entries
  in the MORIZON log tab; they are now `Info`-level when MORIZON itself
  is idle.
- Fixed the in-dialog version label drifting from the actually-installed
  version across several test builds; it now reads `metadata.txt`
  directly and cannot drift again.
- Fixed duplicate MORIZON toolbar icons and leftover toolbar entries
  after disabling/re-enabling the plugin.
- Fixed a false "unexpected count column" warning in the aggregation
  diagnostic log caused by Shapefile's 10-character DBF field-name
  truncation (`count_NODATA` → `count_NODA`); cosmetic only, aggregation
  output itself was never affected.

### Packaging / documentation

- `metadata.txt`'s `about` field now discloses this plugin's external
  dependencies (GDAL, NumPy, matplotlib, and the GRASS Processing
  Provider for two of the six elements).
- Added `test_data/ZoningKit_SYNTH/`, a small, fully synthetic,
  redistributable (GPL-3.0-only) regression dataset, as an alternative
  to the real-world `Zoningkit_SAMPLE` data whose redistribution rights
  are unconfirmed.
- `experimental` reverted to `False` for this release (it was
  temporarily `True` during the `rc3-devN` diagnostic series).

### Known issues

- **スコアリングタブのQML生成が、ごくまれに失敗することがあります**
  （"QML内に連続値カラーランプが見つかりません"）。原因未確定・再現条件不明
  の断続的な事象です。発生した場合は該当要素の再計算をお試しください。
  (Intermittent scoring-tab QML generation failure, root cause and
  trigger condition not identified; workaround is to recalculate the
  affected element. Monitoring continues — see `docs/OPEN_ISSUES.md` O-19.)
- A full confusion-matrix comparison of final zoning output against an
  actual run of the original (pre-port) MORIZON has not been performed
  in this environment (no access to the original's required legacy
  SAGA/GRASS/QGIS stack or its original input data). Individual formula
  fixes (above) were each verified against real reference implementations
  (SAGA, GRASS) directly; see `docs/OPEN_ISSUES.md` O-03 for what remains
  open.
- The GRASS-Processing-Provider-missing preflight check's actual
  on-screen behavior has not been exercised on-device (verified by code
  review only); see `docs/OPEN_ISSUES.md` O-04.

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

## Development history: rc3-dev1 through rc3-dev18 (internal diagnostic builds)

The entries below are the internal, dev-by-dev diagnostic log kept during
the `2.3.0-rc3-devN` series (2026-09-17 to 2026-10-09) while tracking down
the issues fixed in the `2.3.0` release above. None of these builds were
released independently; they are kept here for traceability (which build
introduced or confirmed which fix) rather than as separate releases.

## 2.3.0-rc3-dev18 — 2026-10-09 (test build, not yet released)

Housekeeping pass over the remaining release-gate items (O-01, O-06, O-07,
O-08, O-16) after dev17's on-device testing (print layout, repeat
execution/file locks, Japanese/space paths) all passed. No processing
code changed in this build.

- (O-08) `metadata.txt`: `experimental=False` → `True`. This is a
  diagnostic/test build, not the final v2.3.0 release (see the README
  banner), so marking it stable was inconsistent with its own stated
  status. Revisit at the actual final release.
- (O-01) Confirmed README.md's QGIS version references already agree
  with `metadata.txt` (`qgisMinimumVersion=3.44`) throughout -- the
  mismatch recorded in the original handoff doc no longer exists in
  this tree. No change needed.
- (O-16) Reviewed this session's on-device screenshots (several full
  QGIS window captures from the dev17 testing rounds) for the
  rc3-dev2-era toolbar-duplication issue; no duplicate MORIZON icon
  appeared in any of them. Recorded as a visual review (推定), not a
  dedicated repro test (確定), in `docs/OPEN_ISSUES.md`.

## 2.3.0-rc3-dev17 — 2026-10-09 (test build, not yet released)

Found by the user during dev16 on-device testing (`Zoningkit_SAMPLE` data,
Windows/QGIS 3.44), while checking the SHC and 地利 statistics the O-24
and O-23 fixes above were expected to change.

### Fixed

- (O-25) The scoring tab's "統計値表示" button failed with
  `RuntimeError: x must be a sequence` for every element, instead of
  opening the stats/histogram dialog. `forest_zoning_scoring_stats_dialog.py`'s
  `redraw_graph()` passed a bare scalar `float` to `Line2D.set_xdata()`
  on the line matplotlib's `axvline()` returns; the matplotlib version
  bundled with QGIS 3.44 requires an array-like argument there (older
  versions tolerated a scalar). Fixed by passing the same 2-element
  `[x, x]` form `axvline()` itself uses internally — this works
  regardless of matplotlib version.
- This is unrelated to O-23/O-24: `forest_zoning_scoring_stats_dialog.py`
  was last touched at the `v2.3.0-rc2` release, before any of this
  session's work, and is a pure display/API-compatibility fix — no
  analysis formula, threshold, or raster output is affected.
- Not yet exercised on-device.

## 2.3.0-rc3-dev16 — 2026-10-09 (test build, not yet released)

**On-device confirmation (2026-10-09, `Zoningkit_SAMPLE` data, Windows/QGIS 3.44):**
the user ran element calculation and checked the scoring tab's threshold-init
log. 地形の複雑さ (O-24): Min/Max went from 0.0022468054667115/0.022249130532146
(dev12) to 0.0012491731904447/0.013662728480995 (dev16) — a reduction to
~55.6%/~61.4%, matching the ~0.585 median ratio found during the
SAGA-comparison verification above. 地利 (O-23): Min/Max
(0.0/1316.0926513672) matched dev12 exactly, as expected since this
dataset's road network is fully inside the DEM extent. Both fixes behaved
as predicted on real data.

Follow-up to O-23 (found during the same original-vs-ported source diff
review as O-24, above): `processes/raster_writer/distance.py` rasterized
the road network directly onto the DEM's own grid before computing
proximity with `gdal.ComputeProximity`. When the road network did not
fully cover the DEM extent, this burned zero pixels, and
`ComputeProximity` filled the *entire* output with a "no target pixel"
sentinel value (observed as 65535) rather than correct distances or
NoData — confirmed by reproducing it with a synthetic DEM and a real
GDAL/GRASS installation (same environment used for O-24). The user asked,
before any fix, whether changing this would risk losing fidelity to the
original MORIZON's actual behavior; that was checked first (see below),
and only approved for implementation afterward.

### Fixed

- (O-23) Distance is now computed on the union of the DEM extent and the
  road network's extent — snapped to the DEM's own pixel grid — matching
  what the original MORIZON's `grass7:r.grow.distance` step actually did
  (compute on a region covering both extents, then resample down to the
  DEM grid). Because the union grid shares the DEM's resolution and pixel
  alignment, the DEM's own window is extracted by exact integer-pixel
  crop rather than resampling, avoiding resampling-induced imprecision
  rather than introducing it.
- Verified with the same real SAGA/GRASS/GDAL installation used for O-24,
  on synthetic test cases:
  - Road fully inside the DEM extent (the ordinary case): the new logic
    is numerically **identical** (0 difference) to the previous
    direct-DEM-grid logic. No behavior change for ordinary data.
  - Road extending beyond the DEM extent: the new logic matches a real
    GRASS `r.grow.distance` run on the same union grid to floating-point
    precision (max diff ~6.5e-05 m), resolving the bug while staying
    faithful to what the original actually computed.
  See `docs/OPEN_ISSUES.md` (O-23) for the full verification data,
  including an earlier, misleading comparison that initially suggested a
  ~10 m discrepancy and turned out to be an apples-to-oranges mistake in
  the verification script (inconsistent `ALL_TOUCHED` rasterization
  option between the two sides being compared), not a real one.
- Not yet exercised on-device.

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

