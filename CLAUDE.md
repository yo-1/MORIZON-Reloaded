# MORIZON Reloaded - Claude Code development instructions

## Mission

Maintain and complete MORIZON Reloaded, an unofficial GPL-3.0-only compatibility port of the original Forestry Agency MORIZON QGIS plugin. The immediate baseline is `v2.3.0-rc2`. Preserve the original forestry-zoning formulas, thresholds, score meanings, file names, and four-quadrant classification unless the user explicitly approves a methodological change.

## Repository layout

This repository uses a **flat layout**: the plugin source (`__init__.py`, `metadata.txt`, `processes/`, etc.) lives directly at the repository root, not inside a `MORIZON/` subfolder. `docs/`, `scripts/`, and `prompts/` sit alongside it at the root. Only the **distribution ZIP** produced by `scripts/build_plugin_zip.py` wraps the plugin files inside a top-level `MORIZON/` folder, because QGIS requires the installed plugin folder name to match the plugin ID. Do not read "`MORIZON/xxx`" in older handoff notes as a repository path — treat it as the ZIP-internal path.

## Authoritative baseline

- Runtime target: QGIS 3.44.x Solothurn on Windows, QGIS-bundled Python 3.12.
- Source of truth for code: this repository's root directory.
- Functional specification: the Forestry Agency's official "もりぞん操作マニュアル" manual. It is **not committed to this repository** (redistribution rights unconfirmed); see `docs/REFERENCE_CATALOG.md` for how to obtain and use it.
- Release/attribution rules: `README.md`, `NOTICE`, `LICENSE`, `CHANGELOG.md` (repository root).
- Handoff status and open decisions: `docs/HANDOFF.md` and `docs/OPEN_ISSUES.md`.

## Non-negotiable constraints

1. Do not silently alter analysis formulas, thresholds, NoData rules, raster alignment, CRS treatment, output names, score direction, or zone numbering.
2. Separate compatibility/stability fixes from scientific-method changes. A method change requires a design note, expected impact, comparison data, and explicit user approval.
3. Keep `GPL-3.0-only` and preserve original and Reloaded attribution headers.
4. The plugin folder inside an install ZIP must remain exactly `MORIZON/`; do not wrap it in another directory.
5. Avoid direct PyQt imports; use `qgis.PyQt`. Assume QGIS APIs are unavailable in ordinary CI.
6. Treat Windows file locks, Japanese paths, spaces in paths, Shapefile sidecars, and repeated execution as first-class test cases.
7. Do not claim a QGIS workflow passes unless it was actually run in QGIS and recorded in `docs/TEST_RECORD.md`.

## Required work pattern

Before editing:

1. Read `docs/HANDOFF.md`, `docs/ARCHITECTURE.md`, `docs/VALIDATION.md`, and the relevant source modules.
2. State whether the proposed change is UI, compatibility, processing stability, packaging, documentation, or methodology.
3. Identify affected outputs and regression checks.

After editing:

1. Run `python scripts/static_check.py`.
2. Run any pure-Python tests added for the changed logic.
3. For QGIS-affecting changes, follow `docs/VALIDATION.md` on the Windows QGIS test machine.
4. Update `docs/TEST_RECORD.md` with environment, dataset, observed result, and evidence.
5. Update `CHANGELOG.md` and `metadata.txt` (repository root) only when the release scope is agreed.
6. Build with `python scripts/build_plugin_zip.py` and inspect the ZIP root.

## Definition of done for final v2.3.0

- Clean installation from ZIP in a clean QGIS 3.44.x Windows profile.
- Full six-element workflow, scoring, zoning, aggregation, and print layout complete without uncaught errors.
- Output names, grid, CRS, NoData behavior, score ranges, and zone classes match the accepted reference run.
- Repeat-run and file-lock tests pass.
- Metadata, README, NOTICE, LICENSE, and changelog agree on version, supported QGIS versions, status, and attribution.
- The release ZIP contains only the `MORIZON/` top-level plugin directory and no caches, logs, local paths, credentials, or test data that cannot be redistributed.

## Communication with the user

Write progress and decisions in Japanese. Distinguish these labels explicitly: `確定`, `推定`, `未確認`, `要判断`. Never turn prior conversational information into a verified test result without evidence.
