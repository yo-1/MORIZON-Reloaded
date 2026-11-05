# MORIZON Reloaded統括（ChatGPT）への報告

依頼日: 2026-11-04 / 実施完了日: 2026-11-05 JST

PR #19のJSON解析修正はWindows実機で成功しました。6要素は166.4秒で完走し8出力を生成しました。ただしSHCの極端な最大値を観測したため、数値の科学的妥当性は未確認です。次の判断ではJSON解析修正の合否とSHC/入力品質の調査を分けてください。

対象PR: https://github.com/yo-1/MORIZON-Reloaded/pull/19

検証コードHEAD: caf74c3b7cb5166e7b389873a2d6c548abee7f0e

記録用ローカルブランチ: codex/pr19-windows-validation-20261104。検証記録commit e8540212598dde9ff531e4543f651756e20501efをPR #19のfix/gdalinfo-json-robustnessへpush済み。GitHubのPR HEADとリモートSHAの一致、draft/open、mergedAt=nullを確認した。mainは34e9592072eb91925ca2f341616ab31c57a8475bのまま。最終照合の生データはローカル証跡github-final.jsonに保存。

報告書・証跡・TEST_RECORD・O-38のみ更新し、プラグインソース・計算式・評価方法・版番号は変更していません。SetupCheckには修正版を配置した状態で、バックアップからの復元はしていません。


## PR #19 Windows実機検証（Codex、2026-11-05 JST）

- **判定：PR #19のJSON解析修正は成功。6要素計算は完走。出力の構造的有効性は確認、科学的妥当性は未確認。**
- 対象HEAD: `caf74c3b7cb5166e7b389873a2d6c548abee7f0e`（依頼の`2751106`からの差分は文書2ファイルのみ）。PR #19はdraft/open、base main。実行前にリモートHEADを再照合した。
- 実測環境: Windows 11 build 22631、QGIS 3.44.13-Solothurn、Python 3.12.13、Qt 5.15.13/PyQt 5.15.11、GDAL 3.13.2。GRASSインストールのVERSIONNUMBERは8.5.0 exported。QGIS Dev Probe 0.1.2、interactive、execute_code許可、SetupCheckプロファイル。クラウド疑似試験ではなく、同PCの起動中QGIS GUIをMCP経由で実行した。
- 準備: 既存SetupCheckの`python/plugins`と`QGIS`設定フォルダをローカルへコピーしてからPRソースのZIPを配置。ZIP内66ファイルすべてのSHA256が配置先と一致。ZIP SHA256=`64fe4e53b12b04b4b142b4d56facde9f556f8b6c430de8424f8cc995df90831f`。版番号は2.3.3のままの検証候補であり、公開済み2.3.3と区別する。
- 入力: 元の指定DATA/DEMパスにはTIFF本体がなく、利用者が使用を承認した`C:/GIS_data/morizon/作業用/DEM5m_Shimanto_clip_buffer100m.tif`を検証用ASCIIパスへコピー。元とコピーのSHA256=`fdf449a849eb45dfc2b92fc4fb3014a23e1c9e0bf77262dd1affe1524a4a3e71`、87,889,813 bytes。EPSG:6672、5m、8815×5333、NoData=-9999。補助入力は既存四万十町ZoningKitのROAD/CSV/NPP/SRAD/VTEX/TATEMONOをコピーし、ハッシュ一覧を保存。
- 単独実行: Dev Probe `run_algorithm`で`gdal:gdalinfo`（EXTRA=-json）を実行、0.453秒。生HTMLのJSONより前に`TIFFReadDirectoryCheckOrder:Invalid TIFF directory; tags are not sorted in ascending order`警告2件が混入した。
- 比較: 実機で生成した生HTMLに旧処理と同じ`json.loads(raw[5:-6])`を適用すると`Expecting value: line 1 column 1 (char 0)`を再現。配置済みPRの`MORIZON.utils.get_tiff_info()`は同じDEMで正常にCRS/解像度/範囲/NoData/サイズを返した。旧プラグイン全体の再導入試験ではなく、実出力に対する旧解析式との比較である。
- **確定**: 今回のDEM・環境ではTIFF警告混入が旧JSON解析を破壊することと、修正版が処理できること。**推定**: 11月3日の報告も同原因の可能性が高い。**未確認**: 当日の生出力が残っていないため、11月3日の全事象の原因を断定しない。
- 6要素実行: 実プラグインのメイン画面へ検証ZoningKitを設定し、全6チェックを有効にして既存`run_elements()`を呼び出した。NPP/SRAD/VTEXがEPSG:2446・50m、DEMがEPSG:6672・5mという既存警告を保存し、既存の自動整合処理で続行した。計算式や入力ファイル内容の修正はしていない。
- 2026-11-05 00:48:10〜00:50:57 JST、処理ログで166.4秒。DEM情報取得0.3秒、10mリサンプリング1.9秒、地位9.8秒、集材88.8秒、地利4.0秒、SHC30.6秒、傾斜0.6秒、保全30.4秒。`全要素の計算が完了`と終了ダイアログを確認。JSONDecodeError再発なし。GRASS r.neighbors/r.watershed実行を確認。
- 8出力すべてQGIS/GDAL読込成功、Float32、EPSG:6672、4408×2667、10m、同一geotransform、NoData=-9999。有効画素にNaN/Infなし。16表示レイヤーも有効。NoData画素数は要素ごとに異なり、下表のとおり保存した。NoDataの方法論的な正しさを保証する試験ではない。

| 出力 | 最小 | 最大 | 有効画素 | NoData画素 |
|---|---:|---:|---:|---:|
| Y_01_chii_hinoki.tif | 20.5800743 | 24.0435237885 | 6568567 | 5187569 |
| Y_01_chii_karamatsu.tif | 19.8067436 | 26.0464134216 | 6568567 | 5187569 |
| Y_01_chii_sugi.tif | 15.9162092 | 32.0934638977 | 6568567 | 5187569 |
| Y_02_shuzai.tif | 0 | 10 | 6609368 | 5146768 |
| Y_03_chiri.tif | 0 | 2054.09350586 | 6609368 | 5146768 |
| Y_11_chikei.tif | 0.0032489507 | 11540021248 | 6609368 | 5146768 |
| Y_12_keisha.tif | 0 | 72.5923995972 | 6618538 | 5137598 |
| Y_13_hozen.tif | 0 | 1 | 6215956 | 5540180 |

- **要判断**: SHC最大値11,540,021,248は極端に大きく、数値・入力DEMの品質を別件で確認する必要がある。今回のJSON修正だけをもって科学的妥当性や下流の評価結果まで合格にしない。修正・丸め・しきい値変更は行っていない。
- UI応答停止警告（3.1秒、6.3秒、10.2秒等）を含むログは保持。処理完走とは別の既知監視項目として扱い、警告なしとは報告しない。
- 証跡: [実機環境](evidence/pr19-20261105/environment.json)、[gdalinfo生出力](evidence/pr19-20261105/gdalinfo.html)、[旧式/修正版比較](evidence/pr19-20261105/parser-comparison.json)、[全ログ](evidence/pr19-20261105/qgis-log-complete.json)、[出力検査](evidence/pr19-20261105/output-validation.json)、[完了画面](evidence/pr19-20261105/20261105-005132_pr19_six_elements_completed.png)、[結果画面](evidence/pr19-20261105/20261105-005201_pr19_result_map.png)。
- ローカル全証跡・入力コピー・出力・QGISプロジェクト: `C:/Users/Yoichi_Wada/Documents/Github/MORIZON-Reloaded/.validation/pr19-evidence/`。バックアップ: 同配下`backup-SetupCheck/`（プラグイン・QGIS設定、復元未実施。認証DBを含む全プロファイルのバックアップではない）。地理データ・バックアップ・プロジェクトはGitHubへ追加しない。
- 静的確認: 当初PATH上のPython 3.10.8で構文エラーになったが、対象環境のQGIS同梱Python 3.12.13で48ファイルのstatic_checkが成功。これは上記実機実行とは別の補助確認である。
- 限界: 別途案内された検証セットの原本TEST_MATRIX/ZIPは今回未取得。既存文書のP00〜P08全項目合格は主張せず、本依頼の単独gdalinfo・6要素・出力確認を実施した。繰返し計算、旧版全計算との画素比較、スコアリング以降は未実施。
- mainへのmerge、Release、QGIS公式公開は行っていない。
