from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class RawFileRef:
    name: str
    file_id: str | None = None
    modified_time: str | None = None
    size: int | None = None
    md5_checksum: str | None = None

    @property
    def stem(self) -> str:
        return Path(self.name).stem


class Storage(Protocol):
    @property
    def display_location(self) -> str:
        ...

    def list_raw_files(self) -> list[RawFileRef]:
        ...

    def materialize(self, file_ref: RawFileRef) -> Path:
        ...
