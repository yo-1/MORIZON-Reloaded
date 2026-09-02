# MORIZON Reloaded

MORIZON Reloadedは、林業の収益性と山地災害リスクの両面から森林管理の方向性を検討するQGIS用森林ゾーニング支援プラグインです。

**Current release: v2.3.0-rc2 (release candidate for testing; not the final v2.3.0 release)**

林野庁の委託事業を通じて開発・公開された森林ゾーニング支援ツール「もりぞん（MORIZON）」を基礎として、現行QGISで利用できるよう互換性対応を行っています。原版の分析ロジック、計算体系および判定条件を原則として維持し、利用できなくなった処理基盤やAPIを再実装しています。

MORIZON Reloadedは、原版を基礎として和田陽一が個人的な技術的取組として作成・維持する、独立した非公式の互換性対応版です。日本森林技術協会または林野庁による公式改修版、公式リリース、保証もしくはサポート対象ではありません。

全国のDEMを活用した森林ゾーニングの利活用事例として、森林情報オープン化検討委員会その他の説明・研修等で紹介できます。将来的な公式採用、管理主体への移管または組織的な継続開発については、関係者間で別途協議するものとします。

## 対象環境

- QGIS 3.44.x Solothurn
- Windows
- QGIS同梱Python 3.12系
- QGIS Processing、GDAL、NumPy、matplotlib
- 「保全対象を含む流域」の作成では、QGISで利用可能なGRASS Providerが必要です。

`metadata.txt`ではQGIS 3.34以降を指定していますが、公開前の主試験環境はQGIS 3.44.xです。他のQGIS版での動作は保証していません。

## インストール

1. 配布ZIPを展開しないで保存します。
2. QGISを起動します。
3. **プラグイン → プラグインの管理とインストール → ZIPからインストール**を開きます。
4. 配布ZIPを指定してインストールします。

ZIP内部のプラグインフォルダ名は、原版との互換性維持のため`MORIZON`です。

## 基本的な処理順

1. DEMおよび必要な入力データを準備
2. 各YOUSOを作成
3. 収益性スコアリング
4. 災害リスクスコアリング
5. 収益性・災害リスク判定
6. 4象限ゾーニング
7. 必要に応じて集計・印刷レイアウトを作成

入力データの種類、形式、座標参照系、パラメータおよび判定方法は、林野庁が公開する「もりぞん」操作マニュアルを確認してください。

## 原版からの主な互換性対応

- PyQt5直接importを`qgis.PyQt`へ変更
- 旧ProcessingアルゴリズムIDおよびProvider構成への対応
- SAGA/GRASS依存処理の現行QGIS、GDAL、NumPy等による安定化
- 一時ファイル、Windowsファイルロックおよび再実行への対応
- 入出力レイヤの自動設定とQGIS 3.44向けUI調整

これらは実装基盤の互換性対応であり、森林ゾーニング手法を新たに設計するものではありません。

## ライセンス

本ソフトウェアはGNU General Public License version 3（GPL v3）の条件で利用、改変および再頒布できます。詳細は`LICENSE`を参照してください。

ライセンス選択は、G空間情報センターの林野庁公式配布ページが「もりぞん」ツール全体について示すGPL v3の利用・改変・再頒布条件に基づきます。原版の著作権表示およびReloadedでの改変表示は`NOTICE`を参照してください。

## 名称と関係

- Original project: MORIZON
- Compatibility port: MORIZON Reloaded
- Original implementation: MIERUNE Inc.（原版ソースに記載）
- Development and Reloaded modifications: Yoichi Wada（個人的な技術的取組）
- Official Japan Forest Technology Association / Forestry Agency modification: No
- Future official adoption or transfer: Subject to separate consultation

## 免責

本ソフトウェアは、適用法令で認められる範囲において無保証で提供されます。解析結果は、使用するデータ、座標参照系、解像度、パラメータおよび実行環境の影響を受けます。森林管理、災害リスク評価その他の意思決定では、現地条件、最新資料および専門的判断と併せて利用してください。

## 関連情報

- 林野庁「もりぞん」公式配布ページ: https://www.geospatial.jp/ckan/dataset/rinya-morizon-dateset
- MORIZON Reloadedリポジトリ: https://github.com/yo-1/MORIZON-Reloaded
- 不具合報告: https://github.com/yo-1/MORIZON-Reloaded/issues
- 変更履歴: `CHANGELOG.md`
- 著作権・帰属: `NOTICE`
