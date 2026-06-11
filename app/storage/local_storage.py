from __future__ import annotations

import hashlib
from pathlib import Path

from app.storage.base import RawFileRef


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class LocalStorage:
    """Local filesystem adapter with the same boundary planned for Drive."""

    def __init__(self, raw_dir: Path):
        self.raw_dir = Path(raw_dir)

    @property
    def display_location(self) -> str:
        return str(self.raw_dir)

    def list_raw_files(self) -> list[RawFileRef]:
        if not self.raw_dir.exists():
            return []
        extensions = {".csv", ".tsv"}
        return sorted(
            (
                RawFileRef(
                    name=path.name,
                    file_id=str(path.resolve()),
                    modified_time=str(path.stat().st_mtime_ns),
                    size=path.stat().st_size,
                    md5_checksum=_md5(path),
                )
                for path in self.raw_dir.iterdir()
                if path.is_file() and path.suffix.lower() in extensions
            ),
            key=lambda file_ref: file_ref.name.lower(),
        )

    def materialize(self, file_ref: RawFileRef) -> Path:
        path = self.raw_dir / file_ref.name
        if not path.is_file():
            raise FileNotFoundError(f"ローカルrawファイルが見つかりません: {path}")
        return path
