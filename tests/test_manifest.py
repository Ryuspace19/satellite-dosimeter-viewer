from app.storage.base import RawFileRef
from app.utils.manifest import source_file_changed


def test_md5_is_authoritative_when_modified_time_changes():
    record = {
        "status": "decoded",
        "source_file_id": "drive-id",
        "source_modified_time": "old-time",
        "source_size": 100,
        "source_md5_checksum": "same-md5",
    }
    current = RawFileRef(
        name="sample.csv",
        file_id="drive-id",
        modified_time="new-time",
        size=100,
        md5_checksum="same-md5",
    )
    assert source_file_changed(record, current) is False


def test_changed_md5_requires_reprocessing():
    record = {
        "status": "decoded",
        "source_file_id": "drive-id",
        "source_modified_time": "old-time",
        "source_size": 100,
        "source_md5_checksum": "old-md5",
    }
    current = RawFileRef(
        name="sample.csv",
        file_id="drive-id",
        modified_time="new-time",
        size=101,
        md5_checksum="new-md5",
    )
    assert source_file_changed(record, current) is True
