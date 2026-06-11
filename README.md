# 衛星線量計データビューア

Windows上で衛星線量計のCSV/TSVを読み込み、未処理ファイルだけを復号・解析してStreamlitで表示するアプリです。

- ローカルフォルダとGoogle Drive APIに対応
- MOS1/MOS2 Vth、補間値、温度補正、移動平均、一次近似を表示
- manifestで新規・更新・処理済みファイルを管理
- Excel、summary CSV、解析済みCSV、エラーCSVを画面から保存
- 失敗ファイルだけを画面から再試行

rawファイルは読み取り専用として扱い、変更・上書きしません。

## 対応環境

- Windows 10 / 11
- Python 3.11または3.12
- Git for Windows

## 研究室PCへの初回導入

PowerShellで次を実行します。

```powershell
git clone https://github.com/Ryuspace19/satellite-dosimeter-viewer.git
cd satellite-dosimeter-viewer
```

その後、`setup.bat` をダブルクリックします。

セットアップが完了したら、`run_app.bat` をダブルクリックするとアプリが起動します。

```text
http://localhost:8501
```

`.venv` がない状態で `run_app.bat` を実行した場合も、自動的にセットアップが始まります。

## 各PCを最新版へ更新

アプリを終了してから `update_app.bat` をダブルクリックします。

更新処理は次を自動実行します。

1. ローカルのソース変更がないか確認
2. GitHubの`main`ブランチからfast-forward更新
3. Python依存関係を指定バージョンへ更新
4. 全自動テストを実行
5. 成功後、アプリを起動するか確認

次のローカルデータは更新されません。

- `config/credentials.json`
- `data/google_drive_token.json`
- manifest
- Driveキャッシュ
- 復号CSV
- Excelレポート

ソースコードに未コミットの変更がある場合は、安全のため更新を停止します。

## Google Drive APIの初期設定

対象フォルダIDは初期設定済みです。

```text
15tsVcr813IlsPNRl7xntlCVw2IDEQwRX
```

1. Google Cloud ConsoleでGoogle Drive APIを有効化
2. OAuth同意画面を設定
3. 利用アカウントをテストユーザーへ追加
4. OAuthクライアントIDを「デスクトップアプリ」で作成
5. アプリ左側でGoogle Driveを選択
6. ダウンロードしたOAuth JSONを画面から登録
7. 読み込みボタンを押してGoogle認証

Drive権限は読み取り専用です。認証情報とtokenはGitHubへ登録されません。

## データ保存先

ローカルとGoogle Driveの解析結果は分離されます。

- ローカル：`data/decoded`、`data/graph_data`、`data/reports`
- Google Drive：`data/google_drive/decoded`、`data/google_drive/graph_data`、`data/google_drive/reports`

処理済み判定にはファイルID、更新日時、サイズ、MD5を使用します。同名でも内容が変化した場合は更新ファイルとして再処理します。

## 手動テスト

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```
