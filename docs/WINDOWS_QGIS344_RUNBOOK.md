# QGIS 3.44 Windows 実機検証手順（MORIZON Reloaded）

この手順はv2.3.3のZIPを検証するものです。公開済みの版はv2.3.2（QGIS公式プラグインリポジトリ）、GitHub最新Releaseはv2.3.1です。
配布用ZIPと検証用ZIPを取り違えないよう、検証用ZIP内の`MANIFEST_SHA256.txt`と
PowerShellの`Get-FileHash`でプラグインZIPのSHA-256を照合してください。

## 事前準備

1. 検証用ZIPを展開します。QGISに指定するのは、その中の`plugin/MORIZON_Reloaded_QGIS344_v2.3.3.zip`です。検証用ZIP自体をQGISへ指定しないでください。
2. QGIS 3.44.xの**新しいユーザープロファイル**を作成し、そのプロファイルで起動します。既存のMORIZON 2.3.1と混在させないでください。
3. QGISの「ヘルプ→QGISについて」で完全版番号を確認します。Processingツールボックスに`grass:r.watershed`または`grass7:r.watershed`があることを確認します。
4. `synthetic/ZoningKit_SYNTH`を`C:\GIS_data\MORIZON_validate\ZoningKit_SYNTH`など、書込み可能なローカルフォルダにコピーします。`YOUSO`と`ZONING`は空の出力先です。

PowerShellでのZIP確認例（実際の展開場所へ移動して実行）:

```powershell
Get-FileHash .\plugin\MORIZON_Reloaded_QGIS344_v2.3.3.zip -Algorithm SHA256
Get-Content .\MANIFEST_SHA256.txt
```

## 1. インストールと起動

「プラグイン→プラグインの管理とインストール→ZIPからインストール」で**内側のプラグインZIP**を選びます。MORIZON Reloadedを有効化し、メニューとアイコンからダイアログを開き、閉じて再度開きます。無効化→再有効化とQGIS再起動後の起動も確認します。失敗した場合は、その時点の画面とMORIZONログを保存します。

## 2. 合成データで全工程

入力欄は次のファイルを選びます。パラメータは初期値のままにし、変更した場合は記録してください。

| 入力 | ファイル |
|---|---|
| DEM | `DATA/DEM/DEM_SYNTH.tif` |
| NPP | `DATA/SiteIndex/NPP/NPP_SYNTH.tif` |
| SRAD | `DATA/SiteIndex/SRAD/SRAD_SYNTH.tif` |
| VTEX | `DATA/SiteIndex/VTEX/VTEX_SYNTH.tif` |
| 既設路網 | `DATA/ROAD/romou_SYNTH.shp` |
| 建物 | `DATA/TATEMONO/tatemono_SYNTH.shp` |
| 作業システムCSV | `DATA/SAGYO-SYSTEM_CSV/sagyou_SYNTH.csv` |

1. **要素計算 E01–E06**: 6要素をすべて選択し、出力先を`YOUSO`にして実行します。各出力が作られ、エラーで停止しないことを確認します。
2. **スコアリング S01**: 収益性・災害リスクを実行します。スコア画像と`params.json`、しきい値表示、凡例を確認します。
3. **ゾーニング Z01**: 出力先を`ZONING`にして実行します。`zoning.tif`のゾーン値と`thresholds.json`を確認します。合成データで4種類すべてのゾーンが出るとは限りません。
4. **集計 A01**: ゾーニング図と対象ポリゴンを指定して実行します。統計属性付きShapefileと件数を確認します。
5. **印刷 P01**: ゾーニング図とゾーン統計量の印刷レイアウトをそれぞれ作成し、地図・凡例・文字・縮尺の表示を確認します。両レイアウトのスクリーンショットを残します。

   **同名レイヤーの選び方**: 再実行後は、選択欄に「ゾーン統計量」が複数並ぶことがあります。候補にマウスを重ね、ツールチップの末尾に表示される実ファイル名を確認してください。例えば`aggregate_v2.shp`を使う場合は、そのパスを示す候補を選びます。表示名や候補の上下だけで判断しないでください。ツールチップが見えない場合は、QGISレイヤーパネルで該当レイヤーのプロパティを開き、「情報」のデータソースを確認します。「ゾーニング図」欄も、レイヤ自動設定後に「災害リスク」など別のラスターが選ばれていないか確認し、今回の`zoning.tif`または`zoning_vN.tif`を指定してください。

   **画面の戻り方**: 修正版ではレイアウト編集画面を閉じるとMORIZONの印刷タブへ戻れます。プラグインを再起動せずに、もう一方のレイアウトを作成できることを確認してください。
6. **繰り返し実行 R01**: 要素計算は同名グループがQGISに残っていると実行を止めます。まず要素グループを1つだけQGISのレイヤーパネルから削除し、その要素を同じ出力先で再実行します。次にプロジェクトを別名保存し、要素グループだけを削除して6要素を再実行します。ディスク上の出力ファイルとスコアリング・ゾーニング・集計のレイヤーは残します。その後スコアリング、ゾーニング、集計も再実行し、ファイルロック時の世代付き出力と異常終了がないことを確認します。各タブの入力レイヤーは実行前に確認してください。
7. **パス検証 R02**: 日本語を含むフォルダへ合成データの`DATA`だけをコピーして一括読み込みし、「ファイルパスに全角文字列が含まれています」と表示され実行が安全にブロックされることを確認します。これは原版からの仕様です。次に半角スペースだけを含むASCIIフォルダ（例:`C:\GIS_data\MORIZON test\ZoningKit_SYNTH`）へコピーし、6要素を実行します。日本語パスで全工程を実行する試験ではありません。

作業後、QGISのPythonコンソールに次を貼り付け、ファイル選択で同梱の`windows_validation_snapshot.py`を指定します。続くダイアログで**`YOUSO`と`ZONING`の両方を含む親フォルダ**を選びます。スクリプトは`DATA`内の入力画像を除外します。比較できる旧出力フォルダが無ければ、次のダイアログはキャンセルしてください。`MORIZON_validation_snapshot.json`が選んだフォルダに生成されます。

```python
from qgis.PyQt.QtWidgets import QFileDialog
import runpy
p = QFileDialog.getOpenFileName(None, "windows_validation_snapshot.pyを選択", "", "Python (*.py)")[0]
runpy.run_path(p, run_name="__main__")
```

合成データと`Zoningkit_SAMPLE`は別々の出力フォルダに保存し、それぞれスナップショットを作成してください。既存出力との画素比較は、以前の出力を保存したフォルダを基準として選んだ場合にだけ行われます。比較元が無い場合、画素一致は「未確認」と記録します。

## 3. Zoningkit_SAMPLEの再実行と基準比較

手元の`Zoningkit_SAMPLE`入力を使い、別の新規プロジェクトと空の出力フォルダで同じ全工程を実行します。画像で確認された`Zoningkit_SAMPLE_dev12/Zoningkit_SAMPLE`の`YOUSO`と`ZONING`には旧出力があります。旧フォルダを上書きせず、その親フォルダを比較元に選びます。画素比較には、まず`dev12`の`DATA`入力を使ってください。`dev13`の入力を使う場合は、入力ファイルのハッシュを照合して同一か確かめてください。`dev12`は下記の受入済み`dev17`とは異なる版です。画素が不一致でも、それだけで今回の退行とは判定できません。過去の数値基準は`docs/TEST_RECORD.md`の「accepted reference run」です。以下の値と今回の結果を比較してください。

| 対象 | 受入済みの記録値 |
|---|---|
| DEM | 800×599 px、10 m |
| 地位（スギ）Min / Max | 16.058206558228 / 29.147771835327 |
| 集材作業効率 Min / Max | 0.0 / 10.0 |
| 地利 Min / Max | 0.0 / 1316.0926513672 |
| SHC Min / Max | 0.0012491731904447 / 0.013662728480995 |
| 傾斜 Min / Max | 0.002 / 61.559（表示値、小数3桁） |
| 収益性スコア Min / Max | 3.0 / 9.0 |
| 災害リスクスコア Min / Max | 3.0 / 8.0 |
| ゾーニングしきい値 | profit=6、risk=5 |
| ゾーニング | Float32、800×599 px、4クラス |
| 集計 | 436フィーチャー、`count_1`〜`count_4`と`count_NODA` |

これは過去の版で記録された比較値です。差があれば、入力・設定・環境を記録し、原因を調べてください。

## 結果の受け渡し

同梱の`RESULTS_TEMPLATE.md`を埋め、`MORIZON_validation_snapshot.json`、MORIZONログ、両印刷レイアウトのスクリーンショット、失敗があればエラー画面を添えてください。**未実行・スキップ・失敗・成功を区別**してください。元データの再配布が難しい場合、`Zoningkit_SAMPLE`本体は添付不要です。
