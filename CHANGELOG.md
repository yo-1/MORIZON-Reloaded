# Changelog

All notable changes to MORIZON Reloaded are documented here.

## 2.3.0-rc3-dev1 — 2026-09-17 (test build, not yet released)

Stabilization fixes made during the Claude Code handoff, built for Windows
on-device testing (see docs/VALIDATION.md ST01-ST08 and docs/TEST_RECORD.md).
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
