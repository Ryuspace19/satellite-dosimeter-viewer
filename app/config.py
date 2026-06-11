from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import os


DECODER_VERSION = "v1.4-app"
DEFAULT_RAW_DIR = Path(r"C:\Users\ryuai\Desktop\線量計application\生データ")
DEFAULT_DRIVE_FOLDER_ID = "15tsVcr813IlsPNRl7xntlCVw2IDEQwRX"


@dataclass(frozen=True)
class AppPaths:
    project_root: Path
    raw_dir: Path
    decoded_dir: Path
    graph_data_dir: Path
    reports_dir: Path
    manifest_path: Path
    drive_cache_dir: Path
    google_credentials_path: Path
    google_token_path: Path
    google_drive_folder_id: str
    storage_type: str

    @classmethod
    def from_env(cls) -> "AppPaths":
        project_root = Path(__file__).resolve().parents[1]
        raw_dir = Path(os.getenv("DOSIMETER_RAW_DIR", str(DEFAULT_RAW_DIR)))
        data_dir = project_root / "data"
        return cls(
            project_root=project_root,
            raw_dir=raw_dir,
            decoded_dir=data_dir / "decoded",
            graph_data_dir=data_dir / "graph_data",
            reports_dir=data_dir / "reports",
            manifest_path=data_dir / "manifest.json",
            drive_cache_dir=data_dir / "drive_cache",
            google_credentials_path=Path(
                os.getenv(
                    "GOOGLE_DRIVE_CREDENTIALS",
                    str(project_root / "config" / "credentials.json"),
                )
            ),
            google_token_path=Path(
                os.getenv(
                    "GOOGLE_DRIVE_TOKEN",
                    str(data_dir / "google_drive_token.json"),
                )
            ),
            google_drive_folder_id=os.getenv(
                "GOOGLE_DRIVE_FOLDER_ID", DEFAULT_DRIVE_FOLDER_ID
            ),
            storage_type=os.getenv("DOSIMETER_STORAGE", "local").lower(),
        )

    def ensure_output_dirs(self) -> None:
        for path in (
            self.decoded_dir,
            self.graph_data_dir,
            self.reports_dir,
            self.drive_cache_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)

    def for_storage(self, storage_type: str) -> "AppPaths":
        """Return independent output paths for each source.

        Existing local outputs remain in data/ for backward compatibility.
        Google Drive outputs live under data/google_drive/.
        """
        normalized = storage_type.lower()
        if normalized != "google_drive":
            return replace(self, storage_type="local")
        data_dir = self.project_root / "data" / "google_drive"
        return replace(
            self,
            decoded_dir=data_dir / "decoded",
            graph_data_dir=data_dir / "graph_data",
            reports_dir=data_dir / "reports",
            manifest_path=data_dir / "manifest.json",
            drive_cache_dir=data_dir / "drive_cache",
            storage_type="google_drive",
        )
