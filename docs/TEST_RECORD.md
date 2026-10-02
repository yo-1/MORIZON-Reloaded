# 試験記録

## 引継ぎ作成時の機械確認

| 日付 | 環境 | 対象 | 結果 | 限界 |
|---|---|---|---|---|
| 2026-09-17 | Linux / Python 3 | rc2ソース | `compileall`成功 | PyQGIS実行なし |
| 2026-09-17 | Linux | 配布ZIP | ZIP展開成功、最上位`MORIZON/` | QGISインストールなし |
| 2026-09-17 | Linux / Python 3 | 安定化修正後のrc2ソース（processes/__init__.py、siteidx.py/distance.py/utils.py、GRASS/CRS/グリッドのプリフライトチェック） | `static_check.py`・`build_plugin_zip.py`成功。`resolve_writable_output_path()`のpure-Pythonユニット検証4パターン合格 | QGIS実機なし |
| （日時未確認） | Windows / QGIS 3.44.x（版番号未確認） | rc3-dev1〜dev2相当ビルド | サンプルデータで6要素の計算は最終的に完了。ただし**スコアリング/ゾーニングタブを開いてから処理開始までQGIS画面が18〜23秒応答しなくなる**事象を確認（O-15）。ツールバーの同一アイコン重複表示、無効化時のツールバー残留も確認（O-16、rc3-dev2で修正） | 具体的な日時・QGIS/GDAL/GRASS版・入力データ・CRS・ログ原文は未収集。停止時間帯にログが無く原因未特定だったため診断ビルド（dev3〜dev5）を作成 |
| 2026-09-29 | Linux / Python 3 | `feature/rc3-dev5-diagnostic`ブランチ（診断ログ`diag_log.py`追加版）を`claude/morizon-reloaded-dev-xs6ig8`へ統合したツリー | `static_check.py`成功（48ファイル）。`build_plugin_zip.py`成功、ZIP最上位`MORIZON/`のみ66エントリ、`diag_log.py`を含む。ユーザー提供の実際のrc3-dev5配布ZIPと展開後の内容が完全一致することを確認（`diff -rq`差分ゼロ） | QGIS実機での診断ログ取得・UIスレッド停止箇所の特定は未実施（次のWindows実機試験が必要、O-15） |

## O-15 dev6実機再検証（2026-09-30）

- 日時: 2026-09-30
- 実施者: ユーザー
- QGIS / Python / GDAL / GRASS / OS: QGIS 3.44.x（Windows実機、詳細バージョンは画面から未確認）
- プラグイン版・コミット: v2.3.0-rc3-dev6（`QgsProject().instance()` → `QgsProject.instance()`修正入り、コミット`3262f9f`）
- 入力データ・CRS・解像度: サンプルデータ`Zoningkit_SAMPLE`（DEM 800×599px、`C:\gis_data\Zoningkit_SAMPLE\DATA\DEM\DEM_SAMPLE.tif`）
- 操作手順: プラグイン有効化（無題のプロジェクト、MORIZON未操作の状態を含む）→要素計算（6要素：siteidx, cost, distance, shc, slope, savearea）実行→スコアリング（収益性・災害リスク）実行→ゾーニング実行（thresholds: profit=6, risk=5）→集計実行（mode=dem、出力`aggregate.shp`）
- 期待結果: 各工程の実処理中（要素計算〜集計）に`UIスレッドが約N秒応答していませんでした`警告が出ない、または大幅に短縮される（dev5では26.6秒の警告があった）
- 実測結果:
  - **要素計算〜スコアリング〜ゾーニング〜集計の実処理中、`UIスレッドが約N秒応答していませんでした`警告はゼロ件**。dev5で確認された26.6秒の停止（`refresh_elements_ui`の繰り返し呼び出しが原因）は解消を確認した。
  - 要素計算は6要素合計20.3秒で完了。うち集材作業効率（GRASS `grass:r.neighbors`×2回、計13.0秒）はバックグラウンド処理スレッド内で実行されており、UIブロックなし（stall警告なし）。
  - 要素計算完了（19:22:52）からスコアリングタブのしきい値算出（19:23:14）まで22秒の間隔があったが、この間もstall警告は出ておらず、UIは応答可能だった（ユーザーのタブ切り替え待ち時間であり、フリーズではないと判断）。
  - ただし、**MORIZONのメインダイアログを開く前**（プラグイン有効化直後、`無題のプロジェクト`の状態）に、`UiStallWatchdog`が7.0秒・77.6秒の停止を記録していた（`UIスレッドが約7.0秒／77.6秒応答していませんでした。重なった計測区間: 未計測の処理`）。「未計測の処理」＝MORIZON内部の`timed()`計測区間に一つも該当しなかったことを意味し、MORIZONの処理コードは一切呼ばれていない時点の停止であるため、今回のQgsProjectパッチとは別要因（他プラグインの初期化、ブラウザパネルの外部データソース接続試行等）による可能性が高いが、原因は未確認（別途`docs/OPEN_ISSUES.md`のO-15に記録済み）。
  - 集計時、`ゾーンヒストグラムの出力: ... count列=['count_1', 'count_2', 'count_3', 'count_4', 'count_NODA']`に続き`想定外のcount列があります: ['count_NODA']`という警告が出た。出力先が`aggregate.shp`（Shapefile）のため、DBFフィールド名10文字制限により`count_NODATA`（12文字）が`count_NODA`（10文字）に切り詰められたことによる、診断ログ側の誤検知と判断（`processes/raster_writer/aggregate.py:68`が`count_NODATA`という完全一致文字列と比較しているため）。実際の集計結果（`ratio_1`〜`4`等）は`count_1`〜`4`のみを参照しており影響なし。未修正（別コミットで対応予定）。
- 判定: 合格（O-15本体：実処理中のUI停止は解消を確認）。ただし、MORIZON操作前の起動直後の停止（別要因の可能性）と`count_NODATA`誤検知は未解決のまま残る。
- ログ・画像・比較表: ユーザー提供のQGISログメッセージパネル（タブ`MORIZON`）全文（テキスト）およびスクリーンショット2枚（ゾーニング図表示、MORIZON Reloadedダイアログ、ログパネル全体）。本ドキュメントには要約のみ記録し、ログ原文は本人保管。
- 備考: `metadata.txt`のバージョン表示（`2.3.0-rc3-dev6`）は今回のスクリーンショットからは直接確認できていない（未確認）。ダイアログ左上に「UNOFFICIAL REVIVAL BUILD / QGIS 3.44」の表示のみ確認。

## QGIS試験テンプレート

### 試験ID

- 日時:
- 実施者:
- QGIS / Python / GDAL / GRASS / OS:
- プラグイン版・コミット:
- 入力データ・CRS・解像度:
- 操作手順:
- 期待結果:
- 実測結果:
- 判定: 合格 / 不合格 / 保留
- ログ・画像・比較表:
- 備考:
