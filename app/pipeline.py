from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from app.analysis.excel_report import write_excel_report
from app.analysis.orbit_analysis import run_analysis
from app.config import AppPaths, DECODER_VERSION
from app.decoder.service import decode_file
from app.storage.base import Storage
from app.storage.local_storage import LocalStorage
from app.utils.manifest import (
    backfill_source_metadata,
    file_metadata,
    find_processed_file,
    load_manifest,
    save_manifest,
    source_file_changed,
    upsert_processed_file,
)


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def rebuild_master_and_report(paths: AppPaths) -> tuple[pd.DataFrame, dict[str, pd.DataFrame] | None]:
    summary_files = sorted(paths.decoded_dir.glob("*_decoded_vth_summary.csv"))
    frames = [pd.read_csv(path) for path in summary_files if path.stat().st_size > 0]
    master = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    master_path = paths.graph_data_dir / "trend_master.csv"
    master.to_csv(master_path, index=False, encoding="utf-8-sig")
    if master.empty:
        return master, None
    results = run_analysis(master)
    results["timeseries"].to_csv(
        paths.graph_data_dir / "trend_master_analyzed.csv",
        index=False,
        encoding="utf-8-sig",
    )
    write_excel_report(results, paths.reports_dir / "mosfet_analysis_results_ja.xlsx")
    return master, results


def _process_file_refs(
    paths: AppPaths,
    storage: Storage,
    raw_files: list,
    files_to_process: list,
    new_file_count: int = 0,
    updated_file_count: int = 0,
    retry_requested_count: int = 0,
    retry_missing_count: int = 0,
) -> dict:
    manifest = load_manifest(paths.manifest_path)
    success_count = 0
    failure_count = 0
    row_error_count = 0

    for source_ref in files_to_process:
        stem = source_ref.stem
        summary_path = paths.decoded_dir / f"{stem}_decoded_vth_summary.csv"
        iv_path = paths.decoded_dir / f"{stem}_decoded_iv_all.csv"
        error_path = paths.decoded_dir / f"{stem}_decode_errors.csv"
        try:
            source_path = storage.materialize(source_ref)
            summary, iv, errors = decode_file(source_path)
            summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
            iv.to_csv(iv_path, index=False, encoding="utf-8-sig")
            if not errors.empty:
                errors.to_csv(error_path, index=False, encoding="utf-8-sig")
                error_value = _relative(error_path, paths.project_root)
            else:
                error_path.unlink(missing_ok=True)
                error_value = None
            row_error_count += len(errors)
            success_count += 1
            upsert_processed_file(
                manifest,
                {
                    "source_file": source_ref.name,
                    **file_metadata(source_ref),
                    "status": "decoded",
                    "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "decoder_version": DECODER_VERSION,
                    "summary_file": _relative(summary_path, paths.project_root),
                    "iv_file": _relative(iv_path, paths.project_root),
                    "error_file": error_value,
                    "decoded_rows": len(summary),
                    "error_rows": len(errors),
                    "bcc_error_rows": int((~summary["bcc_ok"].astype(bool)).sum()) if not summary.empty else 0,
                    "cr_error_rows": int((~summary["cr_ok"].astype(bool)).sum()) if not summary.empty else 0,
                },
            )
            save_manifest(paths.manifest_path, manifest)
        except Exception as exc:
            failure_count += 1
            upsert_processed_file(
                manifest,
                {
                    "source_file": source_ref.name,
                    **file_metadata(source_ref),
                    "status": "failed",
                    "processed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "decoder_version": DECODER_VERSION,
                    "summary_file": None,
                    "iv_file": None,
                    "error_file": None,
                    "error": str(exc),
                },
            )
            save_manifest(paths.manifest_path, manifest)

    master, _ = rebuild_master_and_report(paths)
    manifest = load_manifest(paths.manifest_path)
    return {
        "raw_file_count": len(raw_files),
        "new_file_count": new_file_count,
        "updated_file_count": updated_file_count,
        "processed_this_run_count": len(files_to_process),
        "retry_requested_count": retry_requested_count,
        "retry_missing_count": retry_missing_count,
        "decode_success_count": success_count,
        "decode_failure_count": failure_count,
        "row_error_count": row_error_count,
        "bcc_error_count": int((~master["bcc_ok"].astype(bool)).sum()) if not master.empty else 0,
        "cr_error_count": int((~master["cr_ok"].astype(bool)).sum()) if not master.empty else 0,
        "manifest": manifest,
        "master": master,
    }


def process_new_files(paths: AppPaths, storage: Storage | None = None) -> dict:
    paths.ensure_output_dirs()
    storage = storage or LocalStorage(paths.raw_dir)
    manifest = load_manifest(paths.manifest_path)
    raw_files = storage.list_raw_files()
    files_to_process = []
    new_file_count = 0
    updated_file_count = 0
    manifest_backfilled = False
    for file_ref in raw_files:
        record = find_processed_file(manifest, file_ref.name)
        if record and not source_file_changed(record, file_ref):
            manifest_backfilled |= backfill_source_metadata(manifest, file_ref)
            continue
        files_to_process.append(file_ref)
        if record and record.get("status") == "decoded":
            updated_file_count += 1
        else:
            new_file_count += 1
    if manifest_backfilled:
        save_manifest(paths.manifest_path, manifest)
    return _process_file_refs(
        paths=paths,
        storage=storage,
        raw_files=raw_files,
        files_to_process=files_to_process,
        new_file_count=new_file_count,
        updated_file_count=updated_file_count,
    )


def retry_failed_files(paths: AppPaths, storage: Storage | None = None) -> dict:
    paths.ensure_output_dirs()
    storage = storage or LocalStorage(paths.raw_dir)
    manifest = load_manifest(paths.manifest_path)
    failed_names = {
        item.get("source_file")
        for item in manifest.get("processed_files", [])
        if item.get("status") == "failed" and item.get("source_file")
    }
    raw_files = storage.list_raw_files()
    files_by_name = {file_ref.name: file_ref for file_ref in raw_files}
    files_to_process = [
        files_by_name[name] for name in sorted(failed_names) if name in files_by_name
    ]
    missing_count = len(failed_names) - len(files_to_process)
    return _process_file_refs(
        paths=paths,
        storage=storage,
        raw_files=raw_files,
        files_to_process=files_to_process,
        retry_requested_count=len(failed_names),
        retry_missing_count=missing_count,
    )
