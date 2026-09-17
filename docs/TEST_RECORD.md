# 試験記録

## 引継ぎ作成時の機械確認

| 日付 | 環境 | 対象 | 結果 | 限界 |
|---|---|---|---|---|
| 2026-09-17 | Linux / Python 3 | rc2ソース | `compileall`成功 | PyQGIS実行なし |
| 2026-09-17 | Linux | 配布ZIP | ZIP展開成功、最上位`MORIZON/` | QGISインストールなし |
| 2026-09-17 | Linux / Python 3 | 安定化修正後のrc2ソース（`processes/__init__.py`、`processes/raster_writer/siteidx.py`・`distance.py`・`utils.py`） | `python scripts/static_check.py` 成功（47ファイル）。`resolve_writable_output_path()`のpure-Pythonユニット検証（未存在/削除可/ロック中/二重ロック中の4パターン）全て合格。`python scripts/build_plugin_zip.py` 成功、ZIP最上位`MORIZON/`のみ、65エントリ。 | PyQGIS実行なし。実際のQGIS 3.44.x Windows環境での「地位指数」「地利」計算・Windowsファイルロック再現試験・プラグイン読込エラー表示は未実施（要Windows実機） |
| 2026-09-17 | Linux / Python 3 | プリフライトチェック追加後のrc2ソース（`forest_zoning_main_dialog_elements.py`: GRASS事前確認・地利CRS事前確認・地位指数入力診断） | `python scripts/static_check.py` 成功（47ファイル）。`python scripts/build_plugin_zip.py` 成功、ZIP最上位`MORIZON/`のみ、65エントリ。 | PyQGIS実行なし。`QgsApplication.processingRegistry()`・`QgsRasterLayer`・`QgsVectorLayer`・`get_tiff_info`（`gdal:gdalinfo`）はQGIS環境必須のため実行検証は未実施。GRASS未導入環境、CRS不一致データ、解像度差のあるNPP/SRAD/VTEXでの実際のダイアログ表示・応答性はWindows実機で要確認 |

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
