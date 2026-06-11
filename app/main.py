from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from app.analysis.orbit_analysis import prepare_timeseries
from app.config import AppPaths
from app.pipeline import process_new_files, retry_failed_files
from app.storage.google_drive_storage import (
    GoogleDriveConfigurationError,
    GoogleDriveStorage,
)
from app.storage.local_storage import LocalStorage
from app.ui.dashboard import render_dashboard
from app.utils.manifest import load_manifest


def load_existing(paths: AppPaths) -> pd.DataFrame:
    master_path = paths.graph_data_dir / "trend_master.csv"
    master = pd.read_csv(master_path) if master_path.exists() else pd.DataFrame()
    return prepare_timeseries(master) if not master.empty else pd.DataFrame()


def create_storage(paths: AppPaths, storage_type: str):
    if storage_type == "google_drive":
        return GoogleDriveStorage(
            folder_id=paths.google_drive_folder_id,
            credentials_path=paths.google_credentials_path,
            token_path=paths.google_token_path,
            cache_dir=paths.drive_cache_dir,
        )
    return LocalStorage(paths.raw_dir)


def empty_status(paths: AppPaths, storage_location: str) -> dict:
    return {
        "raw_file_count": 0,
        "new_file_count": 0,
        "updated_file_count": 0,
        "processed_this_run_count": 0,
        "retry_requested_count": 0,
        "retry_missing_count": 0,
        "decode_success_count": 0,
        "decode_failure_count": 0,
        "row_error_count": 0,
        "bcc_error_count": 0,
        "cr_error_count": 0,
        "manifest": load_manifest(paths.manifest_path),
        "storage_location": storage_location,
    }


def main() -> None:
    st.set_page_config(page_title="衛星線量計データビューア", layout="wide")
    base_paths = AppPaths.from_env()

    st.sidebar.header("データ取得設定")
    default_index = 1 if base_paths.storage_type == "google_drive" else 0
    storage_label = st.sidebar.radio(
        "読み込み元",
        ["ローカルフォルダ", "Google Drive"],
        index=default_index,
    )
    storage_type = (
        "google_drive" if storage_label == "Google Drive" else "local"
    )
    paths = base_paths.for_storage(storage_type)
    paths.ensure_output_dirs()
    storage = create_storage(paths, storage_type)

    if storage_type == "google_drive":
        st.sidebar.caption(
            f"DriveフォルダID: {paths.google_drive_folder_id}"
        )
        if paths.google_credentials_path.exists():
            st.sidebar.success("OAuth認証ファイル: 配置済み")
        else:
            st.sidebar.warning(
                "OAuth認証ファイルが未配置です。"
                " config/credentials.json を配置してください。"
            )
            uploaded_credentials = st.sidebar.file_uploader(
                "OAuthクライアントJSONを登録",
                type=["json"],
                help=(
                    "Google Cloud Consoleで作成した"
                    "「デスクトップアプリ」のOAuth JSONを選択します。"
                ),
            )
            if uploaded_credentials is not None:
                try:
                    credentials_data = json.loads(
                        uploaded_credentials.getvalue().decode("utf-8")
                    )
                    if not (
                        isinstance(credentials_data, dict)
                        and "installed" in credentials_data
                    ):
                        raise ValueError(
                            "デスクトップアプリ用OAuth JSONではありません。"
                        )
                    paths.google_credentials_path.parent.mkdir(
                        parents=True, exist_ok=True
                    )
                    paths.google_credentials_path.write_text(
                        json.dumps(credentials_data, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    st.sidebar.success(
                        "認証ファイルを保存しました。画面を再読み込みします。"
                    )
                    st.rerun()
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                    st.sidebar.error(f"認証ファイルを保存できません: {exc}")
        if paths.google_token_path.exists():
            st.sidebar.success("Google Drive: 認証済み")
        else:
            st.sidebar.info(
                "初回読み込み時にGoogle認証画面が開きます。"
            )
    else:
        st.sidebar.caption(f"ローカル: {paths.raw_dir}")

    session_key = f"status_{storage_type}"
    status = st.session_state.get(
        session_key,
        empty_status(paths, storage.display_location),
    )

    if st.button("Driveから最新データを読み込み", type="primary"):
        try:
            with st.spinner("新規ファイルを確認し、復号・解析しています..."):
                status = process_new_files(paths, storage)
                status["storage_location"] = storage.display_location
                st.session_state[session_key] = status
            st.success("読み込みと解析が完了しました。")
        except GoogleDriveConfigurationError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.exception(exc)

    current_manifest = load_manifest(paths.manifest_path)
    failed_count = sum(
        item.get("status") == "failed"
        for item in current_manifest.get("processed_files", [])
    )
    if failed_count:
        st.warning(f"再試行可能な失敗ファイルが {failed_count} 件あります。")
        if st.button(
            f"失敗ファイルを再試行（{failed_count}件）",
            type="secondary",
        ):
            try:
                with st.spinner("失敗ファイルを再取得して復号しています..."):
                    status = retry_failed_files(paths, storage)
                    status["storage_location"] = storage.display_location
                    st.session_state[session_key] = status
                if status.get("retry_missing_count", 0):
                    st.warning(
                        "元データが見つからず再試行できなかったファイルが"
                        f" {status['retry_missing_count']} 件あります。"
                    )
                st.success(
                    "再試行が完了しました。"
                    f" 成功 {status['decode_success_count']} 件、"
                    f"失敗 {status['decode_failure_count']} 件"
                )
                st.rerun()
            except GoogleDriveConfigurationError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.exception(exc)

    analyzed = load_existing(paths)
    if not analyzed.empty:
        status["bcc_error_count"] = int(
            (~analyzed["bcc_ok"].astype(bool)).sum()
        )
        status["cr_error_count"] = int(
            (~analyzed["cr_ok"].astype(bool)).sum()
        )
    render_dashboard(st, paths, status, analyzed)


if __name__ == "__main__":
    main()
