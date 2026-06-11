from pathlib import Path

import numpy as np

from app.decoder.frame_decoder import calculate_bcc, decode_frame
from app.decoder.raw_parser import raw_string_to_bytes, read_raw_csv


SAMPLE = Path(r"C:\Users\ryuai\Desktop\線量計application\生データ\DmuLog_20260530_153111.csv")


def test_japanese_columns_and_sample_decode():
    data = read_raw_csv(SAMPLE)
    assert list(data.columns) == ["internal_counter", "datetime_raw", "raw_data"]
    frame = raw_string_to_bytes(data.iloc[0]["raw_data"])
    summary, iv = decode_frame(
        frame,
        {
            "source_file": SAMPLE.name,
            "row_index": 0,
            "internal_counter": data.iloc[0]["internal_counter"],
            "datetime_raw": data.iloc[0]["datetime_raw"],
        },
    )
    assert len(frame) == 253
    assert len(iv) == 82
    assert {row["mos"] for row in iv} == {"MOS1", "MOS2"}
    assert summary["bcc_calc"] == calculate_bcc(frame)
    assert "mos1_vth_interp" in summary


def test_rs_252_bytes_gets_cr():
    payload = b"RS" + bytes(250)
    text = "RS" + payload[2:].hex()
    frame = raw_string_to_bytes(text)
    assert len(frame) == 253
    assert frame[-1] == 0x0D


def test_253_bytes_unchanged():
    payload = b"RS" + bytes(250) + b"\r"
    frame = raw_string_to_bytes(payload.hex())
    assert frame == payload


def test_bcc_error_still_decodes():
    data = read_raw_csv(SAMPLE)
    frame = bytearray(raw_string_to_bytes(data.iloc[0]["raw_data"]))
    frame[250:252] = b"00"
    summary, iv = decode_frame(
        bytes(frame),
        {"source_file": "x.csv", "row_index": 0, "internal_counter": 1, "datetime_raw": "1日 00:00:00"},
    )
    assert summary["bcc_ok"] is False
    assert len(iv) == 82
