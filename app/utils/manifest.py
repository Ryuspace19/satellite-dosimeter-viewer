from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

from app.storage.base import RawFileRef


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"last_loaded_at": None, "processed_files": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"last_loaded_at": None, "processed_files": []}
    data.setdefault("last_loaded_at", None)
    data.setdefault("processed_files", [])
    return data


def save_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".json.tmp")
    temp_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(path)


def find_processed_file(
    manifest: dict[str, Any], source_file: str
) -> dict[str, Any] | None:
    return next(
        (
            item
            for item in manifest.get("processed_files", [])
            if item.get("source_file") == source_file
        ),
        None,
    )


def file_metadata(file_ref: RawFileRef) -> dict[str, Any]:
    return {
        "source_file_id": file_ref.file_id,
        "source_modified_time": file_ref.modified_time,
        "source_size": file_ref.size,
        "source_md5_checksum": file_ref.md5_checksum,
    }


def has_source_metadata(record: dict[str, Any]) -> bool:
    return any(
        record.get(key) is not None
        for key in (
            "source_file_id",
            "source_modified_time",
            "source_size",
            "source_md5_checksum",
        )
    )


def source_file_changed(
    record: dict[str, Any] | None, file_ref: RawFileRef
) -> bool:
    if not record or record.get("status") != "decoded":
        return True
    if not has_source_metadata(record):
        return False

    old_md5 = record.get("source_md5_checksum")
    new_md5 = file_ref.md5_checksum
    if old_md5 and new_md5:
        return old_md5 != new_md5

    old_file_id = record.get("source_file_id")
    if old_file_id and file_ref.file_id and old_file_id != file_ref.file_id:
        return True
    if (
        record.get("source_size") is not None
        and file_ref.size is not None
        and int(record["source_size"]) != int(file_ref.size)
    ):
        return True
    if (
        record.get("source_modified_time") is not None
        and file_ref.modified_time is not None
        and str(record["source_modified_time"]) != str(file_ref.modified_time)
    ):
        return True
    return False


def backfill_source_metadata(
    manifest: dict[str, Any], file_ref: RawFileRef
) -> bool:
    record = find_processed_file(manifest, file_ref.name)
    if (
        not record
        or record.get("status") != "decoded"
        or has_source_metadata(record)
    ):
        return False
    record.update(file_metadata(file_ref))
    return True


def upsert_processed_file(manifest: dict[str, Any], record: dict[str, Any]) -> None:
    items = manifest.setdefault("processed_files", [])
    items[:] = [
        item for item in items if item.get("source_file") != record.get("source_file")
    ]
    items.append(record)
    items.sort(key=lambda item: item.get("source_file", ""))
    manifest["last_loaded_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
