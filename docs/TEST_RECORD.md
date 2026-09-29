# 試験記録

## 引継ぎ作成時の機械確認

| 日付 | 環境 | 対象 | 結果 | 限界 |
|---|---|---|---|---|
| 2026-09-17 | Linux / Python 3 | rc2ソース | `compileall`成功 | PyQGIS実行なし |
| 2026-09-17 | Linux | 配布ZIP | ZIP展開成功、最上位`MORIZON/` | QGISインストールなし |
| 2026-09-17 | Linux / Python 3 | 安定化修正後のrc2ソース（processes/__init__.py、siteidx.py/distance.py/utils.py、GRASS/CRS/グリッドのプリフライトチェック） | `static_check.py`・`build_plugin_zip.py`成功。`resolve_writable_output_path()`のpure-Pythonユニット検証4パターン合格 | QGIS実機なし |
| （日時未確認） | Windows / QGIS 3.44.x（版番号未確認） | rc3-dev1〜dev2相当ビルド | サンプルデータで6要素の計算は最終的に完了。ただし**スコアリング/ゾーニングタブを開いてから処理開始までQGIS画面が18〜23秒応答しなくなる**事象を確認（O-15）。ツールバーの同一アイコン重複表示、無効化時のツールバー残留も確認（O-16、rc3-dev2で修正） | 具体的な日時・QGIS/GDAL/GRASS版・入力データ・CRS・ログ原文は未収集。停止時間帯にログが無く原因未特定だったため診断ビルド（dev3〜dev5）を作成 |
| 2026-09-29 | Linux / Python 3 | `feature/rc3-dev5-diagnostic`ブランチ（診断ログ`diag_log.py`追加版）を`claude/morizon-reloaded-dev-xs6ig8`へ統合したツリー | `static_check.py`成功（48ファイル）。`build_plugin_zip.py`成功、ZIP最上位`MORIZON/`のみ66エントリ、`diag_log.py`を含む。ユーザー提供の実際のrc3-dev5配布ZIPと展開後の内容が完全一致することを確認（`diff -rq`差分ゼロ） | QGIS実機での診断ログ取得・UIスレッド停止箇所の特定は未実施（次のWindows実機試験が必要、O-15） |

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
