from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.decoder.frame_decoder import decode_frame
from app.decoder.raw_parser import raw_string_to_bytes, read_raw_csv


SUMMARY_COLUMNS = [
    "source_file", "row_index", "internal_counter", "datetime_raw", "flag",
    "frame_counter", "frame_len", "temp_x10", "temp_degC", "temp_coef_a",
    "feature_count", "leak1_uA", "leak2_uA", "leak1_mA", "leak2_mA",
    "img_sigma_dn_x10", "img_snr_db_x10", "sigma_dn", "snr_db",
    "mos1_start_code", "mos2_start_code", "mos1_vth", "mos2_vth",
    "mos1_vth_corr", "mos2_vth_corr", "mos1_vth_index", "mos2_vth_index",
    "mos1_id_at_vth_mA", "mos2_id_at_vth_mA", "mos1_vth_interp",
    "mos2_vth_interp", "mos1_vth_interp_corr", "mos2_vth_interp_corr",
    "bcc_recv", "bcc_calc", "bcc_ok", "cr_ok", "decoder_version",
]
IV_COLUMNS = [
    "source_file", "row_index", "internal_counter", "datetime_raw",
    "frame_counter", "mos", "index", "dac_code", "vgs", "id_uA", "id_mA",
    "temp_degC", "temp_coef_a", "vth", "vth_corr", "vth_interp",
    "vth_interp_corr", "bcc_ok", "cr_ok", "decoder_version",
]
ERROR_COLUMNS = [
    "source_file", "row_index", "internal_counter", "datetime_raw",
    "raw_data_head", "error",
]


def decode_file(path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    raw_frame = read_raw_csv(path)
    summaries: list[dict] = []
    iv_rows: list[dict] = []
    errors: list[dict] = []
    for row_index, row in raw_frame.iterrows():
        metadata = {
            "source_file": path.name,
            "row_index": int(row_index),
            "internal_counter": row["internal_counter"],
            "datetime_raw": row["datetime_raw"],
        }
        try:
            frame = raw_string_to_bytes(row["raw_data"])
            summary, points = decode_frame(frame, metadata)
            summaries.append(summary)
            iv_rows.extend(points)
        except Exception as exc:
            errors.append(
                {
                    **metadata,
                    "raw_data_head": str(row["raw_data"])[:80],
                    "error": str(exc),
                }
            )
    return (
        pd.DataFrame(summaries, columns=SUMMARY_COLUMNS),
        pd.DataFrame(iv_rows, columns=IV_COLUMNS),
        pd.DataFrame(errors, columns=ERROR_COLUMNS),
    )
