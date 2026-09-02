# Changelog

All notable changes to MORIZON Reloaded are documented here.

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
