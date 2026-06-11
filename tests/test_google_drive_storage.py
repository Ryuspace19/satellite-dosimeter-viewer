from pathlib import Path

from app.storage.google_drive_storage import GoogleDriveStorage


class FakeRequest:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class FakeFiles:
    def __init__(self):
        self.list_calls = []

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        return FakeRequest(
            {
                "files": [
                    {
                        "id": "csv-id",
                        "name": "DmuLog.csv",
                        "mimeType": "text/csv",
                        "modifiedTime": "2026-06-11T00:00:00Z",
                        "size": "123",
                        "md5Checksum": "abc",
                    },
                    {
                        "id": "txt-id",
                        "name": "memo.txt",
                        "mimeType": "text/plain",
                    },
                ]
            }
        )


class FakeService:
    def __init__(self):
        self.files_resource = FakeFiles()

    def files(self):
        return self.files_resource


def test_drive_lists_only_csv_and_tsv(tmp_path):
    service = FakeService()
    storage = GoogleDriveStorage(
        folder_id="folder-id",
        credentials_path=tmp_path / "credentials.json",
        token_path=tmp_path / "token.json",
        cache_dir=tmp_path / "cache",
        service=service,
    )
    files = storage.list_raw_files()
    assert [item.name for item in files] == ["DmuLog.csv"]
    assert files[0].file_id == "csv-id"
    assert files[0].size == 123
    assert "'folder-id' in parents" in service.files_resource.list_calls[0]["q"]
