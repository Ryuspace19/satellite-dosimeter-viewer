from __future__ import annotations

from io import FileIO
import json
from pathlib import Path

from app.storage.base import RawFileRef


DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
CSV_MIME_TYPES = {
    "text/csv",
    "text/tab-separated-values",
    "application/csv",
    "application/vnd.ms-excel",
}


class GoogleDriveConfigurationError(RuntimeError):
    pass


class GoogleDriveStorage:
    """Read-only Google Drive adapter for one raw-data folder."""

    def __init__(
        self,
        folder_id: str,
        credentials_path: Path,
        token_path: Path,
        cache_dir: Path,
        service=None,
    ):
        self.folder_id = folder_id.strip()
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path)
        self.cache_dir = Path(cache_dir)
        self._service = service
        if not self.folder_id:
            raise GoogleDriveConfigurationError(
                "Google DriveフォルダIDが設定されていません。"
            )

    @property
    def display_location(self) -> str:
        return f"Google Drive folder: {self.folder_id}"

    @property
    def is_authenticated(self) -> bool:
        return self.token_path.exists()

    def _build_service(self):
        if self._service is not None:
            return self._service
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise GoogleDriveConfigurationError(
                "Google Drive用ライブラリが未導入です。"
                " requirements.txtを再インストールしてください。"
            ) from exc

        credentials = None
        if self.token_path.exists():
            try:
                credentials = Credentials.from_authorized_user_file(
                    str(self.token_path), [DRIVE_READONLY_SCOPE]
                )
            except (ValueError, json.JSONDecodeError, OSError):
                credentials = None

        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())

        if not credentials or not credentials.valid:
            if not self.credentials_path.exists():
                raise GoogleDriveConfigurationError(
                    f"OAuth認証ファイルが見つかりません: {self.credentials_path}"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.credentials_path), [DRIVE_READONLY_SCOPE]
            )
            credentials = flow.run_local_server(
                port=0,
                open_browser=True,
                authorization_prompt_message=(
                    "Google Drive認証画面をブラウザで開いています..."
                ),
                success_message=(
                    "Google Drive認証が完了しました。このタブを閉じてアプリへ戻ってください。"
                ),
            )

        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(credentials.to_json(), encoding="utf-8")
        self._service = build(
            "drive", "v3", credentials=credentials, cache_discovery=False
        )
        return self._service

    def list_raw_files(self) -> list[RawFileRef]:
        service = self._build_service()
        query = f"'{self.folder_id}' in parents and trashed = false"
        fields = (
            "nextPageToken,"
            "files(id,name,mimeType,modifiedTime,size,md5Checksum)"
        )
        refs: list[RawFileRef] = []
        page_token = None
        while True:
            response = (
                service.files()
                .list(
                    q=query,
                    fields=fields,
                    pageSize=1000,
                    pageToken=page_token,
                    orderBy="name",
                    spaces="drive",
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )
            for item in response.get("files", []):
                name = item.get("name", "")
                suffix = Path(name).suffix.lower()
                mime_type = item.get("mimeType", "")
                if suffix not in {".csv", ".tsv"} and mime_type not in CSV_MIME_TYPES:
                    continue
                refs.append(
                    RawFileRef(
                        name=name,
                        file_id=item["id"],
                        modified_time=item.get("modifiedTime"),
                        size=int(item["size"]) if item.get("size") else None,
                        md5_checksum=item.get("md5Checksum"),
                    )
                )
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        return sorted(refs, key=lambda file_ref: file_ref.name.lower())

    def materialize(self, file_ref: RawFileRef) -> Path:
        if not file_ref.file_id:
            raise GoogleDriveConfigurationError(
                f"DriveファイルIDがありません: {file_ref.name}"
            )
        service = self._build_service()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        target = self.cache_dir / file_ref.name
        temporary = target.with_suffix(target.suffix + ".download")

        try:
            from googleapiclient.http import MediaIoBaseDownload
        except ImportError as exc:
            raise GoogleDriveConfigurationError(
                "google-api-python-clientが未導入です。"
            ) from exc

        request = service.files().get_media(
            fileId=file_ref.file_id,
            supportsAllDrives=True,
        )
        with FileIO(temporary, "wb") as output:
            downloader = MediaIoBaseDownload(output, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        temporary.replace(target)
        return target
