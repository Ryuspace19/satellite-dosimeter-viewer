import json
from pathlib import Path

from app.config import AppPaths
from app.pipeline import process_new_files, retry_failed_files
from app.storage.base import RawFileRef
from app.storage.local_storage import LocalStorage
from app.utils.manifest import load_manifest


SAMPLE = Path(r"C:\Users\ryuai\Desktop\線量計application\生データ\DmuLog_20260530_153111.csv")


def make_paths(tmp_path, raw_dir):
    return AppPaths(
        project_root=tmp_path,
        raw_dir=raw_dir,
        decoded_dir=tmp_path / "data" / "decoded",
        graph_data_dir=tmp_path / "data" / "graph_data",
        reports_dir=tmp_path / "data" / "reports",
        manifest_path=tmp_path / "data" / "manifest.json",
        drive_cache_dir=tmp_path / "data" / "drive_cache",
        google_credentials_path=tmp_path / "config" / "credentials.json",
        google_token_path=tmp_path / "data" / "google_drive_token.json",
        google_drive_folder_id="test-folder",
        storage_type="local",
    )


def prepare_sample(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    sample_copy = raw_dir / SAMPLE.name
    sample_copy.write_bytes(SAMPLE.read_bytes())
    return raw_dir, sample_copy, make_paths(tmp_path, raw_dir)


def test_manifest_prevents_reprocessing(tmp_path):
    raw_dir, _, paths = prepare_sample(tmp_path)
    first = process_new_files(paths, LocalStorage(raw_dir))
    second = process_new_files(paths, LocalStorage(raw_dir))
    manifest = load_manifest(paths.manifest_path)
    assert first["new_file_count"] == 1
    assert first["updated_file_count"] == 0
    assert second["new_file_count"] == 0
    assert second["updated_file_count"] == 0
    assert manifest["processed_files"][0]["status"] == "decoded"
    assert manifest["processed_files"][0]["source_file_id"]
    assert manifest["processed_files"][0]["source_modified_time"]
    assert manifest["processed_files"][0]["source_size"] > 0
    assert manifest["processed_files"][0]["source_md5_checksum"]
    assert (paths.reports_dir / "mosfet_analysis_results_ja.xlsx").exists()


def test_same_name_changed_content_is_reprocessed(tmp_path):
    raw_dir, sample_copy, paths = prepare_sample(tmp_path)
    first = process_new_files(paths, LocalStorage(raw_dir))
    original_md5 = load_manifest(paths.manifest_path)["processed_files"][0][
        "source_md5_checksum"
    ]

    sample_copy.write_bytes(sample_copy.read_bytes() + b"\r\n")
    second = process_new_files(paths, LocalStorage(raw_dir))
    updated_record = load_manifest(paths.manifest_path)["processed_files"][0]

    assert first["new_file_count"] == 1
    assert second["new_file_count"] == 0
    assert second["updated_file_count"] == 1
    assert second["decode_success_count"] == 1
    assert updated_record["source_md5_checksum"] != original_md5


def test_legacy_manifest_is_backfilled_without_reprocessing(tmp_path):
    raw_dir, _, paths = prepare_sample(tmp_path)
    process_new_files(paths, LocalStorage(raw_dir))
    manifest = load_manifest(paths.manifest_path)
    record = manifest["processed_files"][0]
    for key in (
        "source_file_id",
        "source_modified_time",
        "source_size",
        "source_md5_checksum",
    ):
        record.pop(key, None)
    paths.manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    result = process_new_files(paths, LocalStorage(raw_dir))
    backfilled = load_manifest(paths.manifest_path)["processed_files"][0]

    assert result["new_file_count"] == 0
    assert result["updated_file_count"] == 0
    assert result["decode_success_count"] == 0
    assert backfilled["source_md5_checksum"]


def test_google_drive_profile_uses_independent_outputs(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    local_paths = make_paths(tmp_path, raw_dir)
    drive_paths = local_paths.for_storage("google_drive")

    assert drive_paths.manifest_path != local_paths.manifest_path
    assert drive_paths.decoded_dir != local_paths.decoded_dir
    assert drive_paths.graph_data_dir != local_paths.graph_data_dir
    assert drive_paths.reports_dir != local_paths.reports_dir
    assert "google_drive" in drive_paths.manifest_path.parts


class FlakyStorage:
    def __init__(self, source_path):
        self.source_path = source_path
        self.fail_download = True

    @property
    def display_location(self):
        return "test"

    def list_raw_files(self):
        return [
            RawFileRef(
                name=self.source_path.name,
                file_id="drive-file-id",
                modified_time="2026-06-11T00:00:00Z",
                size=self.source_path.stat().st_size,
                md5_checksum="test-md5",
            )
        ]

    def materialize(self, file_ref):
        if self.fail_download:
            raise RuntimeError("temporary download failure")
        return self.source_path


def test_failed_file_can_be_retried(tmp_path):
    raw_dir, sample_copy, paths = prepare_sample(tmp_path)
    storage = FlakyStorage(sample_copy)

    first = process_new_files(paths, storage)
    failed_manifest = load_manifest(paths.manifest_path)
    assert first["decode_failure_count"] == 1
    assert failed_manifest["processed_files"][0]["status"] == "failed"

    storage.fail_download = False
    retried = retry_failed_files(paths, storage)
    retried_manifest = load_manifest(paths.manifest_path)

    assert retried["retry_requested_count"] == 1
    assert retried["retry_missing_count"] == 0
    assert retried["decode_success_count"] == 1
    assert retried_manifest["processed_files"][0]["status"] == "decoded"
