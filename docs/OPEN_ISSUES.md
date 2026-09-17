# 未解決事項・意思決定台帳

| ID | 状態 | 優先度 | 内容 | 完了条件 |
|---|---|---:|---|---|
| O-01 | 要判断 | 高 | READMEのQGIS 3.34記載とmetadataの3.44指定が不一致 | 支持範囲を決め両者を一致 |
| O-02 | 未確認 | 高 | rc2のクリーン環境フルワークフロー | 全工程の記録と証拠 |
| O-03 | 未確認 | 高 | 旧版比較の入力・評価手順・混同行列 | 再現可能な比較一式を保存 |
| O-04 | 一部対応 | 高 | GRASS provider未導入時の案内品質 | 明確なエラーと復旧手順 |
| O-05 | 要判断 | 中 | rc3を挟むか正式v2.3.0へ進むか | 外部試験結果を踏まえ決定 |
| O-06 | 未確認 | 中 | QGIS公式プラグイン審査向けmetadata | 公式要件との照合 |
| O-07 | 未確認 | 中 | 再配布可能な最小回帰データ | 権利確認済みデータと期待値 |
| O-08 | 要判断 | 中 | `experimental=False`の妥当性 | 公開方針とmetadata一致 |
| O-09 | 一部対応 | 低 | 広い例外捕捉箇所のログ不足 | 重要失敗が追跡可能 |
| O-10 | 未確認 | 低 | QGIS 3.16版QML属性の残存影響 | 3.44で表示確認・必要時限定修正 |
| O-11 | 対応済み | 中 | GRASS Processing Provider未導入時、処理開始前の事前チェックが無い（現状は保全対象流域の実行時に判明） | プリフライトチェックの要否をユーザーが判断 |
| O-12 | 対応済み | 中 | 入力レイヤのCRS不一致が処理途中まで判明しない（distance.py等） | 事前警告の要否をユーザーが判断（自動再投影は不可） |
| O-13 | 保留 | 低 | 作業システムCSVのフォーマット耐性（列数不足・区切り文字違い） | もりぞんCSV仕様との整合を保ったまま改善できるか要検討 |
| O-14 | 対応済み | 中 | 地位指数計算でDEMとNPP/SRAD/VTEXの解像度・CRSが異なる場合、処理内で自動整合されるが事前の可視化が無い | 差分を事前提示し続行可否をユーザーが選べる |

## 変更管理ルール

各課題は、原因、再現条件、変更対象、非変更対象、検証方法、結果を記録する。複数課題を一度に直すコミットを避ける。計算体系に関わる課題は、実装前にユーザーの明示判断を得る。

## O-09 対応記録（2026-09-17）

Claude Code引継ぎ後の初回安定化修正として、以下2点を実施した（計算式・しきい値・CRS処理・出力名には一切触れていない）。

1. **`processes/__init__.py`のサイレントなインポート失敗を解消**。従来は`aggregate`/`elements`/`scoring`/`zoning`/`raster_writer`/`raster_styler`/`printlayout`の読込失敗を`print(e)`のみで握りつぶし、後段で`processes.raster_writer`等への参照が原因不明の`AttributeError`になっていた。QGIS API自体が読めない場合（pure-Python単体テスト等）はこれまで通り無害化する一方、QGIS API読込後のサブモジュール読込失敗は`QgsMessageLog`へ記録したうえで`raise`し直し、プラグイン読込エラーとして明確に失敗するよう変更した。
2. **Windowsファイルロック時の挙動を統一**。`savearea.py`/`shc.py`/`risk.py`/`profit.py`/`zoning.py`は既存出力がロックされていても`_v2`, `_v3`...の世代付きファイルへ自動退避していたが、`siteidx.py`（地位指数）と`distance.py`（地利）だけが`PermissionError`で処理を中断していた。共通ヘルパー`processes/raster_writer/utils.py::resolve_writable_output_path()`を追加し、両ファイルをこれに統一した。「前回の出力をQGISで開いたまま再実行する」という同じ操作で、要素によって成否が分かれる非対称性を解消した。

検証は`docs/TEST_RECORD.md`の該当行を参照。QGIS実機での再現試験は未実施（要Windows実機、O-02と合わせて要確認）。

## O-04・O-11・O-12・O-14 対応記録（2026-09-17）

`forest_zoning_main_dialog_elements.py`の`run_elements()`（要素計算の実行前検証）に、以下3件のプリフライトチェックを追加した。いずれも**警告・情報提示のみ**で、実際の計算ロジック・CRS処理・グリッド整合処理には一切変更を加えていない。

1. **GRASS Processing Provider事前確認（O-04・O-11）**: `_is_grass_watershed_available()`。保全対象流域が選択されている場合、`QgsApplication.processingRegistry()`で`grass:r.watershed`/`grass7:r.watershed`の登録有無を確認する。未導入なら処理開始前に「プラグイン→プラグインの管理とインストール→GRASSを有効化」という具体的な復旧手順を示して中断する。従来は他の要素計算が全て終わった後にGRASSエラーで失敗することがあった。
2. **地利計算のCRS事前確認（O-12）**: `_confirm_distance_crs_consistency()`。地利が選択されている場合、DEMと既設路網データのCRSを事前に比較し、不一致があれば具体的なCRS値と再投影の対処方法を提示して続行可否を確認する。distance.py側の既存チェック（不一致時にRuntimeErrorで停止）はそのまま安全ネットとして残している。
3. **地位指数の入力データ診断（O-14）**: `_confirm_siteidx_grid_alignment()`。地位指数が選択されている場合、DEMとNPP/SRAD/VTEXの解像度・CRSを`utils.get_tiff_info()`で比較し、差があれば具体的な数値を提示する。siteidx.py内の`_align_parameter_to_dem`が処理中に自動整合するため処理は止まらないが、差が大きいほど補間誤差が増える可能性を事前に知らせ、続行可否を確認する。

いずれもGUIスレッド上で`QgsRasterLayer`/`QgsVectorLayer`/`get_tiff_info`（内部で`gdal:gdalinfo`）を呼ぶため、既存の建物CRS確認ダイアログと同様の応答性特性を持つ（大きなファイルではわずかに待ち時間が生じ得るが未確認）。

検証: `python scripts/static_check.py`成功、`python scripts/build_plugin_zip.py`成功（ZIP構造は従来通り）。QGIS実機でのダイアログ表示・実際のGRASS未導入環境・CRS不一致データでの動作確認は未実施（要Windows実機）。
