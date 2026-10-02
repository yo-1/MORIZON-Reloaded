# GitHub・Claude Codeへの移行記録

このファイルは、ハンドオフパッケージ作成時点の「移行手順(案)」を、実際に採用した内容へ更新したものです。今後同様の引継ぎを行う場合の参考として残します。

## 採用した構成(確定)

- 新規リポジトリは作成せず、既存の `https://github.com/yo-1/MORIZON-Reloaded` をそのまま継続利用した。
- 作業ブランチは `claude/morizon-reloaded-dev-xs6ig8`(ハンドオフパッケージ案の`handoff/claude-v2.3.0-rc2`は不採用)。
- **ディレクトリ構造はフラット構造を採用**(プラグイン本体をリポジトリルート直下に置いたまま)。ハンドオフパッケージが前提としていた`MORIZON/`サブフォルダへの移動は行っていない。理由は次の通り。
  - 既に公開されているリポジトリの構造を変えると、大規模なファイル移動コミットになり、コミット履歴の追跡性が下がる。
  - 個人開発のQGISプラグインでは、リポジトリを直接QGISのプラグインディレクトリへシンボリックリンクして開発する運用が一般的で、フラット構造の方が相性が良い。
  - QGIS公式が要求するのは「配布ZIPのトップレベルフォルダ名がプラグインIDと一致すること」のみで、リポジトリ内部の構成は問わない。配布ZIP生成時に`scripts/build_plugin_zip.py`が`MORIZON/`名でラップする。
- リポジトリのソースコードは、ハンドオフパッケージ同梱のrc2ソースと`diff`で完全一致することを確認済み。新たなソース反映作業は不要だった。

## GitHubへ含めたもの

- `CLAUDE.md`、`docs/`、`scripts/`、`prompts/`、`.gitignore`(いずれもフラット構造向けにパス表記を調整)
- 既存のREADME、NOTICE、LICENSE、CHANGELOG、metadata.txt(変更なし)

## GitHubへ含めなかったもの(方針を維持)

- 著作権・再配布条件を確認していない参考PDF(操作マニュアル等)
- 大容量の試験データ、個人情報、ローカルパス入りログ
- `dist/`の生成物(Release添付へ回す)
- ハンドオフパッケージの`original/`(rc2 ZIP原本)
- QGISプロファイル、キャッシュ、`__pycache__`

参考PDFは引き続き手元で保管し、GitHub公開前に権利と必要性を個別に確認すること。

## 追記: ブランチの分岐と統合（2026-09-29）

2026-09-17のセッション終了後、**別のセッションが`main`から独立して`feature/rc3-dev3-diagnostic`〜`feature/rc3-dev5-diagnostic`を作成**し、`claude/morizon-reloaded-dev-xs6ig8`とは別系統でrc3-dev1相当の安定化修正を再実装したうえ、Windows実機テストで判明した不具合（ツールバー重複表示、UI応答停止等）への対応を重ねていた。両ブランチは共通祖先`9c83255`から分岐したまま一度もマージされていなかった。

2026-09-29、ユーザーの判断で実機テスト・不具合修正が反映された`feature/rc3-dev5-diagnostic`を正とし、`claude/morizon-reloaded-dev-xs6ig8`をその内容で作り直した（`git checkout -B claude/morizon-reloaded-dev-xs6ig8 origin/feature/rc3-dev5-diagnostic`）うえで、本ページを含む引継ぎ資料一式を再度統合した。旧ブランチの内容（rc3-dev1相当、引継ぎ資料の初回整備のみ）は失われないよう`backup/claude-dev-xs6ig8-rc3-dev1`ブランチとしてGitHub上に保存してある。詳細な経緯は`docs/OPEN_ISSUES.md`の「ブランチ統合の経緯」を参照。

教訓: 複数のセッション・エージェントが同一リポジトリに対して並行作業する場合、着手前に`git fetch --all && git branch -a`で他ブランチの有無を確認すること。ブランチ名や配布ZIPのバージョン番号が独立に進んでいると、この時のように4バージョン分（dev1→dev5）気づかないまま乖離しうる。
