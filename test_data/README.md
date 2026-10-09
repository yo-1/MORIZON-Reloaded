# test_data/ — 再配布可能な最小回帰データセット（O-07）

## これは何か

`ZoningKit_SYNTH/`は、MORIZON Reloadedの動作確認・回帰テスト用に作成した、**完全に合成（synthetic）の最小データセット**です。地形（DEM）・地位指数の入力（NPP/SRAD/VTEX）・建物ポリゴン・既設路網ライン・作業システムCSVは、すべて数式またはリポジトリに既存のGPL-3.0-onlyコード内のサンプル値から生成されています。

**実在する地点の測量成果・地形・施設情報とは一切関係がありません**。林野庁の配布データ（`Zoningkit_SAMPLE`等、再配布権が未確認）とは別物であり、このリポジトリと同じGPL-3.0-onlyの下でそのまま再配布できます。

## 構成

`docs/HANDOFF.md`「5. 入力データとフォルダ契約」に記載の標準フォルダ構造に準拠しています。

```text
ZoningKit_SYNTH/
├─ DATA/
│  ├─ DEM/DEM_SYNTH.tif                 80x60セル、10m解像度、EPSG:6677
│  ├─ ROAD/romou_SYNTH.shp              既設路網ライン2本（DEM範囲内に収まる）
│  ├─ SAGYO-SYSTEM_CSV/sagyou_SYNTH.csv 作業システムCSV（costcsv_parser.pyの
│  │                                     docstring記載サンプル値をそのまま使用）
│  ├─ SiteIndex/
│  │  ├─ NPP/NPP_SYNTH.tif
│  │  ├─ SRAD/SRAD_SYNTH.tif
│  │  └─ VTEX/VTEX_SYNTH.tif            いずれもDEMと同一グリッド・同一解像度
│  └─ TATEMONO/tatemono_SYNTH.shp       建物ポリゴン3棟
├─ YOUSO/   （要素計算の出力先。空、.gitkeepで追跡）
└─ ZONING/  （ゾーニング・集計の出力先。空、.gitkeepで追跡）
```

## 作り方（再生成）

```bash
python3 scripts/generate_regression_test_data.py
```

Linux環境でも実行できます（QGIS不要、GDAL/OGR Pythonバインディングのみ必要）。既存ファイルは上書きされます。数式・座標は固定値のため、再実行しても同一のデータが生成されます（決定的）。

## 使い方

QGISにMORIZON Reloadedをインストールした状態で、`DATA/`配下の各ファイルを要素計算タブの入力欄に設定し、通常どおり要素計算→スコアリング→ゾーニング→集計を実行できます。作業システムCSVの`shc_param`等の設定値はMORIZON側のデフォルトのままで構いません。

## 位置づけ（Definition of doneとの関係）

このデータセット自体は「入力データ」のみを提供します。`docs/HANDOFF.md`・`CLAUDE.md`が言う「accepted reference run（受入済みの基準出力）」は、**人が実際にQGIS実機で一度処理を実行し、その結果を承認する**ことで初めて成立します。このデータセットを使って最初に実機実行した結果を、`docs/TEST_RECORD.md`に記録・承認することで、以降の回帰比較の基準値にできます。

## データサイズ

合計 約176KB（ラスター4枚、ベクタ2レイヤー、CSV1件）。公式QGISプラグインリポジトリのZIPサイズ上限（20〜25MB）に対して無視できる大きさです。
