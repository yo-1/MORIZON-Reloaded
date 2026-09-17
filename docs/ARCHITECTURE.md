# アーキテクチャ概観

## エントリポイントとUI

| 領域 | 主ファイル | 責務 |
|---|---|---|
| プラグイン登録 | `__init__.py` | QGISからのclassFactory |
| ライフサイクル | `forest_zoning.py` | メニュー、ツールバー、ダイアログ起動 |
| メインUI | `forest_zoning_main_dialog.py`, `.ui` | タブ・主要画面 |
| 要素計算 | `forest_zoning_main_dialog_elements.py` | 入力探索、要素処理、レイヤ登録 |
| スコアリング | `forest_zoning_main_dialog_scoring.py` | しきい値、点数化、2軸作成 |
| ゾーニング | `forest_zoning_main_dialog_zoning.py` | 2軸しきい値、4区分作成 |
| 集計 | `forest_zoning_main_dialog_aggregate.py` | ポリゴン単位集計 |
| 印刷 | `forest_zoning_main_dialog_printlayout.py` | QPTからレイアウト作成 |
| 設定 | `forest_zoning_settings_dialog.py`, `settings_manager.py` | パラメータ・保存設定 |

すべて本リポジトリのルート直下に配置される(フラット構造。`MORIZON/`という子フォルダは存在しない)。

## 処理層

- `processes/raster_writer/`: 数値ラスター・ベクタ出力
- `processes/raster_styler/`: QGISレンダラーと表示
- `processes/scoring.py`: 要素点数化と合成
- `processes/zoning.py`: 4象限分類
- `processes/aggregate.py`: ゾーン統計
- `processes/printlayout/`: 印刷テンプレート読込
- `processes/elements.py`: 要素処理の共通調整
- `processes/costcsv_parser.py`: 作業システムCSV読込

## 重要な依存境界

QGIS/PyQGIS、Processing provider、GDAL/OGR、NumPy、matplotlibに依存する。保全対象流域はGRASS providerも必要。一般Python環境で確認できるのは構文、ファイル構造、メタデータ整合、QGIS非依存ロジックに限定される。

## 変更時の影響判定

- `raster_writer`変更: 数値結果・NoData・グリッドの回帰試験が必須
- `raster_styler`変更: 数値値を変えないことを確認し、凡例・色・閾値を視覚確認
- UI変更: `.ui`とPython側objectNameの対応、Tab順、長い日本語、Windows高DPIを確認
- 定数変更: 入出力契約と既存ZoningKit互換性を確認
- metadata/README変更: 公開版番号・対応QGIS・実験版状態を全ファイルで一致させる
