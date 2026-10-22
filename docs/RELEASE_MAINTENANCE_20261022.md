# 配布物・Release・ブランチ整理記録 v1.0

確認日：2026-10-22（JST）

## 現在の基準

- GitHub Release / ソースタグ：v2.3.3
- タグのコミット：a63fd86057c1e35dee17a28cb693b9ff82fe9b4c
- mainはPR #16で公開案内を更新済み。文書更新前後のmainと配布タグは区別する。
- QGIS承認済み版：v2.3.2。v2.3.3はユーザーの提示画面・報告で審査中（同日）。
- QGISでの承認とGitHubでの公開は別の状態。

## v2.3.3配布ZIPの実測

取得元：https://github.com/yo-1/MORIZON-Reloaded/releases/download/v2.3.3/MORIZON_Reloaded_QGIS344_v2.3.3.zip

ファイル名：MORIZON_Reloaded_QGIS344_v2.3.3.zip
容量：389536 bytes
SHA-256：6a211ebde1d95934f4eff4500ebca7ac83e08ed01004789ff68c3e6cca102e70

GitHubのasset digestとダウンロード実測値が一致。ZIP CRC正常。ZIP内の全66ファイルをv2.3.3タグの各パスとバイト比較し、全件一致した。
QGISに提出したZIPとのバイト一致は未確認。QGISの該当版ダウンロードへの取得試行はHTTP 403。既存の接続資料から提出ZIPは確保できていない。

実機試験記録のe81fff9由来ZIPのハッシュ f3297734c6b10203c4944dcee9e4ef907a41587f140ee4aeaab1378b3ced7a6c は別物であり、提出ZIPのハッシュの代用にしない。今回の確認はZIPとソースの同一性確認で、実機試験の再実行ではない。

## v2.3.2 Releaseの説明訂正案（画面への反映は未実施）

> QGIS公式リポジトリのv2.3.2と、提供ZIPの全66プラグインファイルが一致するソースを記録したタグです。タグは824acca0a60ac553714faef0ba7c83d42f47404aを指し、プラグイン内容は最初の一致コミット2c74dcf3d48ce85c323aca9b2ac34ef9419b9bdfと同一です。
>
> 2026-10-22更新：この系統はPR #12（統合コミット1b2774388efe472f68a2aad2107367fe0cbae138）とPR #14を通じてmainへ統合済みです。後続のGitHub Releaseはv2.3.3です。従来の「mainには未統合」は作成時点の記述で、現在には当てはまりません。
>
> このReleaseにはインストール用ZIPは添付されていません。Source code (zip)はQGISインストール用ZIPではありません。

既存タグを移動せず、上記説明のみを更新する方針。Pre-release属性の変更は今回行っていない。

## 残存ブランチの役割と処置

| ブランチ | 調査時HEAD | 役割・判断 | 処置 |
| --- | --- | --- | --- |
| main | 61acd2cb70477054f07734c789c73233d899c0cb | 現行保守の基準 | 維持 |
| claude/morizon-reloaded-dev-xs6ig8 | bac1db5fdc7993d8c1740bc368b4bac7d0ae504a | v2.3.0～2.3.1移行時の開発履歴。mainとはコミット履歴が分岐。過去のsquash統合もあり、ahead件数だけで未統合機能と判定しない | 開発用途は終了候補。削除前にarchiveタグ等でHEADを恒久保存 |
| codex/windows-ci-stage-1 | cd5548abf364183752a961770263d414568b8294 | 初期Windows CI。現行mainには別途復旧・更新済みのWindows CIが存在。旧ブランチ独自の2コミットあり | 新規統合しない。保存後の削除候補 |
| codex/windows-validation-download | 5ab600cab90f3fbdf6f24ec4f3e7ac04e4325c77 | 旧2.3.1/2.3.2検証用ZIPをdistに保持。現行Release配布には使用しない | 検証履歴として保存後の削除候補 |

上記3ブランチは単純なmainの祖先ではないため、保全せず一括削除していない。現行mainへ旧ZIPや旧CIをマージする必要はない。
この記録作成前の確認時点で未完了PRは0件。履歴は消さず、今後の実装はmainを起点に作業ごとの短期ブランチとし、マージ後に整理する。

## 実施上の残り

1. QGIS提出ZIPの実体またはそのSHA-256を得て上記GitHub asset実測値と比較する。
2. v2.3.2 Release本文を上記訂正案で更新する。
3. 旧3ブランチHEADをarchiveタグ等で保全し、旧ブランチ名を削除する。直前にHEAD・進行中PRの変動を再確認する。

今回利用できたGitHub接続にはRelease本文編集・タグ作成・ブランチ削除の機能がない。ブラウザー接続も利用できず、2・3は実行未了。ツールの制約を理由に未実行操作を完了扱いにしない。
