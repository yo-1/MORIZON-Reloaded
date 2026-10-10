# 検証計画

## 1. 静的確認

```bash
python scripts/static_check.py
python scripts/build_plugin_zip.py
```

静的確認はQGIS実行試験の代替ではない。

アップロードする**そのZIP**に対して、公開前に次も実行する。専用のPython環境で
`python -m pip install flake8==7.4.1 bandit==1.9.4 detect-secrets==1.5.0`を実行し、
その環境のPythonを使う。ZIPの版とパスを実際の候補に合わせる。

```bash
python scripts/preflight_plugin_zip.py dist/MORIZON_Reloaded_QGIS344_v2.3.1.zip
```

ZIP構造・メタデータ・Python構文、Flake8、Banditの中高リスク、detect-secretsを確認する。
Flake8などの指摘が残れば終了コード1となる。QGIS公式サイトの検査器とは設定が異なり、
件数が一致する保証はない。QGISの実行試験、画像比較、GitHubチェックの代替でもない。
Qt6互換性チェックも対象外であり、QGIS公式サイトでのQt6結果を別に確認する。
2026-10-11時点のv2.3.1公開ZIPではFlake8が923件で、この検査は不合格となる。
`codex/plugin-preflight`で再生成した同版名の試験ZIPはFlake8/Bandit/秘密情報が
いずれも0件だが、公開済みZIPとは内容が異なる。Flake8は日本語文とQMLリテラルを
保持するため行長上限160文字とし、3つのQMLテンプレートモジュールだけ行長規則を
除外する。他の規則は維持する。正式な再公開には版更新とQGIS 3.44実機確認が必要。

GitHub Actionsの3ジョブはFlake8/構文、ZIP/セキュリティ、Debian 13上のQGIS 3.40
モジュール読み込みを検証する。Qt6の104件相当の列挙値を新しい参照形式へ変更したが、
公式サイトのQt6チェックは次のZIPをアップロードするまで確認できない。QGIS 3.40での
モジュール読み込みはQGIS 3.44 Windowsでの処理結果検証の代替ではない。

## 2. 対象環境

- Windows 10または11
- QGIS 3.44.x Solothurn（64bit、通常インストーラ）
- 新規ユーザープロファイル
- GRASS providerを利用可能にする
- 日本語・空白を含むデータパスとASCIIのみのパスの双方

記録項目: QGIS完全版番号、GDAL、GRASS、Python、OS build、プラグイン版、入力データ識別子、CRS、実行日時。

入力データは、権利関係が確認できている`test_data/ZoningKit_SYNTH/`（完全に合成されたデータ、GPL-3.0-onlyで再配布可能、O-07）を使うか、別途入手した`Zoningkit_SAMPLE`等の配布データを使う。前者は再配布可能な最小データセットとして、CIや他環境での再現にも使える。

## 3. スモーク試験

- ZIPからインストールできる
- 有効化・無効化・再有効化できる
- メニューとアイコンから起動できる
- ダイアログを閉じて再度開ける
- QGIS再起動後も起動できる

## 4. 機能試験

| ID | 処理 | 主な合格条件 |
|---|---|---|
| E01 | 地位3樹種 | 3出力、同一グリッド、妥当なNoData |
| E02 | 集材作業効率 | CSVを解釈し整数カテゴリを出力 |
| E03 | 地利 | 道路からの距離関係が正しい |
| E04 | SHC | 旧版/基準出力との相関・差分を記録 |
| E05 | 傾斜 | 単位、範囲、グリッドを確認 |
| E06 | 保全対象流域 | GRASS処理、CRS、建物交差、NoDataを確認 |
| S01 | スコアリング | 各軸3～9点、params.json生成 |
| Z01 | ゾーニング | 4クラス、thresholds.json生成 |
| A01 | 集計 | 入力ポリゴンに統計属性が追加 |
| P01 | 印刷 | ゾーニング/統計レイアウトが作成される |

## 5. 回帰試験

各GeoTIFFについて、サイズ、geotransform、CRS、NoData、データ型、最小/最大、カテゴリ別画素数、差分率、相関係数を保存する。カテゴリ出力は相関だけでなく一致率と混同行列を使う。

合格閾値は旧版との差の原因を説明できるまでは固定しない。既報値を自動的な合格基準にしてはならない。

## 6. 異常系

- CRS未定義/不一致
- 必須ファイル欠落、同候補複数、破損CSV
- 1m/5m/10m DEM、大規模DEM
- 出力ファイルをQGISで開いたまま再実行
- 書込権限なし、長いパス、日本語、空白、OneDrive配下
- GRASS providerなし
- 処理キャンセル後の再実行

## 7. 証拠

`docs/TEST_RECORD.md`へ結果を記録し、ログ、比較CSV、スクリーンショットの相対パスを添える。証拠がない項目は「未確認」とする。
