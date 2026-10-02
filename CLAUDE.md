# MORIZON Reloaded - Claude Code development instructions

## Mission

Maintain and complete MORIZON Reloaded, an unofficial GPL-3.0-only compatibility port of the original Forestry Agency MORIZON QGIS plugin. The last officially released version is `v2.3.0-rc2`; the current Windows on-device test build on this branch is `v2.3.0-rc3-dev5` (see `CHANGELOG.md` and `docs/OPEN_ISSUES.md` O-15 for the open freeze/UI-stall investigation this build exists to diagnose). Preserve the original forestry-zoning formulas, thresholds, score meanings, file names, and four-quadrant classification unless the user explicitly approves a methodological change.

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

1. Read `docs/HANDOFF.md`, `docs/ARCHITECTURE.md`, `docs/VALIDATION.md`, `docs/OPEN_ISSUES.md`, and the relevant source modules.
2. Run `git fetch --all && git branch -a` and check for other in-progress branches before assuming this branch is the latest state. On 2026-09-29 a parallel session diverged for 12 days (`feature/rc3-dev3-diagnostic` through `-dev5`) with real Windows on-device fixes that this branch did not have; see `docs/OPEN_ISSUES.md` ("ブランチ統合の経緯") and `docs/GITHUB_MIGRATION.md` for what happened and why. Do not assume a version-number suffix (`rc3-devN`) uniquely identifies a branch.
3. State whether the proposed change is UI, compatibility, processing stability, packaging, documentation, or methodology.
4. Identify affected outputs and regression checks.

After editing:

1. Run `python scripts/static_check.py`.
2. Run any pure-Python tests added for the changed logic.
3. For QGIS-affecting changes, follow `docs/VALIDATION.md` on the Windows QGIS test machine.
4. Update `docs/TEST_RECORD.md` with environment, dataset, observed result, and evidence.
5. Update `CHANGELOG.md` and `metadata.txt` (repository root) only when the release scope is agreed.
6. Build with `python scripts/build_plugin_zip.py` and inspect the ZIP root.

## 現在地の更新確認

このリポジトリは、claude.ai・Claude Codeなど複数のセッション／エージェントが並行して触ることがある。2026-09-29には、この非同期作業により`claude/morizon-reloaded-dev-xs6ig8`と`feature/rc3-dev3-diagnostic`〜`-dev5`が12日間分岐したまま気づかれなかった事例がある（詳細は`docs/GITHUB_MIGRATION.md`・`docs/OPEN_ISSUES.md`「ブランチ統合の経緯」を参照）。同じ失敗を繰り返さないため、作業開始時・終了時に以下を徹底する。

### 作業開始前

1. `git fetch --all && git branch -a`で全ブランチを確認する。ブランチ名やバージョン番号のサフィックス（`rc3-devN`等）だけで「これが最新」と判断しない。
2. GitHub上のPR一覧（open/closed双方）を確認し、進行中のPRのbase/head・draft状態・最終更新時刻を把握する。
3. `docs/OPEN_ISSUES.md`・`docs/TEST_RECORD.md`・`docs/HANDOFF.md`を読む。
4. 他のセッション（例：claude.ai側の会話）から「現在地メモ」のような引継ぎ文書を渡された場合、その内容は**そのセッションが最後に確認した時点のスナップショット**であり、必ずGitHubの実際の状態（ブランチ・PRのSHA、open/closed状態）と照合する。一致しない、または照合できない項目は「未確認」として扱い、メモの記述をそのまま確定事実として引用しない。

### 作業終了時

1. コミット・pushしたら、push成功メッセージだけで終わらせず、**リモート側のSHAとGitHub側の表示（コミット履歴・PR画面）**まで確認する。
2. `docs/OPEN_ISSUES.md`・`docs/TEST_RECORD.md`など、状況を追跡するドキュメントを更新する。次にどのセッションが開いても、GitHub上の記録だけで現在地が分かる状態にしておく。
3. 同じブランチを他のセッションが同時に触っている可能性を考慮する。他セッションの作業を上書きしうる操作（force-with-lease push、ブランチの作り直し等）は、実行前にユーザーへ確認する。

### Claude Codeからclaude.aiへの伝達

Claude Codeセッションが、claude.ai側のセッションへ伝えたい情報（このセッション固有の作業内容、次に確認・実施してほしいこと、判明した注意点等）を持つ場合は、Markdownファイルを作成し、**「これをclaude.aiに伝えてください」と明示してユーザーへ提示する**。ユーザーがそれをコピーしてclaude.ai側の会話に貼り付けることを想定した、自己完結した文書にする（確定/推定/未確認を区別すること、GitHubの実状態と照合可能な情報を含めることは他の節と同様）。

### PR運用の注意（過去の失敗から）

- PR説明文のコミット表は、最後のコミットをpushした後に`git log`から作成する。コミット追加後に表を更新し忘れない。
- PR本文は生のMarkdownテキストを渡す・貼る。GitHub画面の表示からコピーするとHTMLタグが混入することがある。

## Definition of done for final v2.3.0

- Clean installation from ZIP in a clean QGIS 3.44.x Windows profile.
- Full six-element workflow, scoring, zoning, aggregation, and print layout complete without uncaught errors.
- Output names, grid, CRS, NoData behavior, score ranges, and zone classes match the accepted reference run.
- Repeat-run and file-lock tests pass.
- Metadata, README, NOTICE, LICENSE, and changelog agree on version, supported QGIS versions, status, and attribution.
- The release ZIP contains only the `MORIZON/` top-level plugin directory and no caches, logs, local paths, credentials, or test data that cannot be redistributed.

## Communication with the user

Write progress and decisions in Japanese. Distinguish these labels explicitly: `確定`, `推定`, `未確認`, `要判断`. Never turn prior conversational information into a verified test result without evidence.
