# 配布物・Release・ブランチ整理記録 v1.2

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
2026-10-22追記：QGIS提出ZIPの照合依頼に応じてユーザーが添付した同名ZIPを実測。容量389536 bytes、SHA-256は上記と一致し、GitHubから取得したZIPとバイト単位でも完全一致した。内部版2.3.3、experimental=False、最上位MORIZON/、66ファイル、CRC正常。ユーザー提供の提出物との照合として完了。QGISサーバーに保管されたファイル自体の再取得はHTTP 403のため未実施であり、審査承認やサーバー側原本の独立検証を意味しない。

実機試験記録のe81fff9由来ZIPのハッシュ f3297734c6b10203c4944dcee9e4ef907a41587f140ee4aeaab1378b3ced7a6c は別物であり、提出ZIPのハッシュの代用にしない。今回の確認はZIPとソースの同一性確認で、実機試験の再実行ではない。

## v2.3.2 Releaseの説明訂正内容（Release本文への反映確認済み）

> QGIS公式リポジトリのv2.3.2と、提供ZIPの全66プラグインファイルが一致するソースを記録したタグです。タグは824acca0a60ac553714faef0ba7c83d42f47404aを指し、プラグイン内容は最初の一致コミット2c74dcf3d48ce85c323aca9b2ac34ef9419b9bdfと同一です。
>
> 2026-10-22更新：この系統はPR #12（統合コミット1b2774388efe472f68a2aad2107367fe0cbae138）とPR #14を通じてmainへ統合済みです。後続のGitHub Releaseはv2.3.3です。従来の「mainには未統合」は作成時点の記述で、現在には当てはまりません。
>
> このReleaseにはインストール用ZIPは添付されていません。Source code (zip)はQGISインストール用ZIPではありません。

2026-10-22、ユーザーがRelease本文を更新。保存後の提示画面とGitHub APIの本文で、main統合済み・後続v2.3.3への訂正を確認した。タグは移動せず、Pre-release=Trueを維持。

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

1. 完了：照合依頼に対してユーザーが提供したv2.3.3提出ZIPとGitHub assetの実測ハッシュ・バイト列が一致。QGIS承認は別工程。
2. 完了：ユーザーによるv2.3.2 Release本文更新をGitHub APIで確認。
3. 旧3ブランチHEADをarchiveタグ等で保全し、旧ブランチ名を削除する。直前にHEAD・進行中PRの変動を再確認する。

今回利用できたGitHub接続にはRelease本文編集・タグ作成・ブランチ削除の機能がない。ブラウザー接続も利用できず、3は実行未了（2はユーザーが画面で更新し、APIで確認済み）。ツールの制約を理由に未実行操作を完了扱いにしない。
