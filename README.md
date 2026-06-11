# 衛星線量計データビューア

Windows上で衛星線量計のCSV/TSVを読み込み、未処理ファイルだけを復号・解析してStreamlitで表示するアプリです。

読み込み元は画面から次の2種類を選択できます。

- ローカルフォルダ
- Google Drive API

rawファイルは読み取り専用として扱い、変更・上書きしません。

## セットアップ

PowerShellでプロジェクトフォルダへ移動して実行します。

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## 起動

```powershell
python -m streamlit run app\main.py
```

または `run_app.bat` をダブルクリックします。

ブラウザで次を開きます。

```text
http://localhost:8501
```

## ローカルフォルダ

既定の読み込み先です。

```text
C:\Users\ryuai\Desktop\線量計application\生データ
```

別のフォルダを使う場合：

```powershell
$env:DOSIMETER_RAW_DIR = "D:\dosimeter\raw"
```

## Google Drive APIの初期設定

対象フォルダIDは初期設定済みです。

```text
15tsVcr813IlsPNRl7xntlCVw2IDEQwRX
```

Google Cloud側で一度だけOAuthクライアントを作成します。

1. Google Cloud Consoleを開く。
2. 新規または既存プロジェクトを選択する。
3. 「APIとサービス」からGoogle Drive APIを有効化する。
4. OAuth同意画面を設定する。
5. テスト運用の場合は、利用するGoogleアカウントをテストユーザーへ追加する。
6. 「認証情報を作成」からOAuthクライアントIDを作成する。
7. アプリケーションの種類は「デスクトップアプリ」を選択する。
8. ダウンロードしたJSONを `config/credentials.json` として配置する。

その後、アプリ画面で次を実行します。

1. 左側の「読み込み元」で「Google Drive」を選択する。
2. 「Driveから最新データを読み込み」を押す。
3. 初回だけ開くGoogle認証画面で、共有Driveを閲覧できるアカウントを選択する。
4. Driveの読み取り権限を許可する。

認証後のtokenは次へ保存されます。

```text
data/google_drive_token.json
```

`credentials.json` とtokenは `.gitignore` 対象で、GitHubにはコミットされません。Drive権限は読み取り専用です。

環境変数で設定を変更できます。

```powershell
$env:DOSIMETER_STORAGE = "google_drive"
$env:GOOGLE_DRIVE_FOLDER_ID = "フォルダID"
$env:GOOGLE_DRIVE_CREDENTIALS = "C:\path\credentials.json"
$env:GOOGLE_DRIVE_TOKEN = "C:\path\google_drive_token.json"
```

## 処理内容

- 日本語列名 `カウンタ`、`蓄積時刻`、`ログ` に対応
- CSV/TSVと複数文字コードに対応
- MOS1/MOS2のVth、補間Vth、温度補正、I-V全点を復号
- BCC/CR異常を記録
- `manifest.json` で処理済みファイルを管理
- 温度・画像指標・Vthのグラフ表示
- Vthの任意期間移動平均と一次近似を表示
- 日/週/任意期間集計とExcelレポートを生成
- 失敗ファイルだけを画面から再試行
- Excel、summary CSV、解析済みCSV、復号エラーCSVを画面からダウンロード

Google Drive使用時は、Drive上の一覧を取得した後、未処理CSV/TSVだけを `data/google_drive/drive_cache` へダウンロードして処理します。

ローカルとGoogle Driveの解析結果は混在しません。

- ローカル: `data/decoded`, `data/graph_data`, `data/reports`
- Google Drive: `data/google_drive/decoded`, `data/google_drive/graph_data`, `data/google_drive/reports`

処理済み判定には次のメタデータを使用します。

- Google DriveファイルID
- 更新日時
- ファイルサイズ
- MD5チェックサム

同じファイル名でもMD5が変化した場合は更新ファイルとして再処理します。更新日時だけが変わりMD5が同じ場合は再処理しません。旧形式のmanifestは、初回確認時に再復号せずメタデータだけを補完します。

## 出力

- `data/decoded/*_decoded_vth_summary.csv`
- `data/decoded/*_decoded_iv_all.csv`
- `data/decoded/*_decode_errors.csv`
- `data/graph_data/trend_master.csv`
- `data/graph_data/trend_master_analyzed.csv`
- `data/reports/mosfet_analysis_results_ja.xlsx`
- `data/manifest.json`

## テスト

```powershell
pytest -q
```
