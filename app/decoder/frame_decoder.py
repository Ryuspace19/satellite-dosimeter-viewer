from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from app.config import DECODER_VERSION
from app.decoder.vth import calculate_vth, calculate_vth_interp


FRAME_LEN = 253
FRAME_LEN_NO_CR = 252
MOS_WINDOW_SIZE = 84
N_POINTS = 41
VDD_DAC = 5.0
DAC_LSB = VDD_DAC / 4096.0
DAC_STEP_CODE = 5
TEMP_COEF_A = -0.003411429
T_REF = 25.0


def uint16_le(lo: int, hi: int) -> int:
    return (hi << 8) | lo


def int16_le(lo: int, hi: int) -> int:
    value = uint16_le(lo, hi)
    return value - 0x10000 if value >= 0x8000 else value


def uint32_le(values: bytes) -> int:
    return int.from_bytes(values, byteorder="little", signed=False)


def calculate_bcc(frame: bytes) -> str:
    value = 0
    for byte in frame[:250]:
        value ^= byte
    return f"{value:02X}"


@dataclass
class MosDecoded:
    start_code: int
    dac_code: np.ndarray
    vgs: np.ndarray
    id_uA: np.ndarray
    id_mA: np.ndarray
    vth: float
    vth_index: int | None
    id_at_vth_mA: float
    vth_interp: float


def decode_mos_window(window: bytes) -> MosDecoded:
    if len(window) != MOS_WINDOW_SIZE:
        raise ValueError(f"MOS window長が不正です: {len(window)}")
    start_code = uint16_le(window[0], window[1])
    id_uA = np.array(
        [int16_le(window[2 + i * 2], window[3 + i * 2]) for i in range(N_POINTS)],
        dtype=float,
    )
    indices = np.arange(N_POINTS)
    dac_code = start_code + DAC_STEP_CODE * indices
    vgs = dac_code * DAC_LSB
    id_mA = id_uA / 1000.0
    vth, vth_index, id_at_vth_mA = calculate_vth(vgs, id_mA)
    vth_interp = calculate_vth_interp(vgs, id_mA)
    return MosDecoded(
        start_code=start_code,
        dac_code=dac_code,
        vgs=vgs,
        id_uA=id_uA,
        id_mA=id_mA,
        vth=vth,
        vth_index=vth_index,
        id_at_vth_mA=id_at_vth_mA,
        vth_interp=vth_interp,
    )


def decode_frame(frame: bytes, metadata: dict) -> tuple[dict, list[dict]]:
    if len(frame) != FRAME_LEN:
        raise ValueError(f"フレーム長が不正です: {len(frame)}")
    if frame[:2] != b"RS":
        raise ValueError("フレームヘッダーがRSではありません")

    mos1 = decode_mos_window(frame[4:88])
    mos2 = decode_mos_window(frame[88:172])
    temp_x10 = int16_le(frame[172], frame[173])
    temp_degC = temp_x10 / 10.0
    feature_count = uint32_le(frame[174:178])
    leak1_uA = int16_le(frame[178], frame[179])
    leak2_uA = int16_le(frame[180], frame[181])
    sigma_raw = int16_le(frame[182], frame[183])
    snr_raw = int16_le(frame[184], frame[185])
    sigma_dn = np.nan if sigma_raw == -32768 else sigma_raw / 10.0
    snr_db = np.nan if snr_raw == -32768 else snr_raw / 10.0
    bcc_recv = frame[250:252].decode("ascii", errors="replace")
    bcc_calc = calculate_bcc(frame)
    bcc_ok = bcc_recv.upper() == bcc_calc.upper()
    cr_ok = frame[252] == 0x0D

    def corrected(value: float) -> float:
        return value - TEMP_COEF_A * (temp_degC - T_REF) if not math.isnan(value) else np.nan

    summary = {
        **metadata,
        "flag": frame[2],
        "frame_counter": frame[3],
        "frame_len": len(frame),
        "temp_x10": temp_x10,
        "temp_degC": temp_degC,
        "temp_coef_a": TEMP_COEF_A,
        "feature_count": feature_count,
        "leak1_uA": leak1_uA,
        "leak2_uA": leak2_uA,
        "leak1_mA": leak1_uA / 1000.0,
        "leak2_mA": leak2_uA / 1000.0,
        "img_sigma_dn_x10": sigma_raw,
        "img_snr_db_x10": snr_raw,
        "sigma_dn": sigma_dn,
        "snr_db": snr_db,
        "mos1_start_code": mos1.start_code,
        "mos2_start_code": mos2.start_code,
        "mos1_vth": mos1.vth,
        "mos2_vth": mos2.vth,
        "mos1_vth_corr": corrected(mos1.vth),
        "mos2_vth_corr": corrected(mos2.vth),
        "mos1_vth_index": mos1.vth_index,
        "mos2_vth_index": mos2.vth_index,
        "mos1_id_at_vth_mA": mos1.id_at_vth_mA,
        "mos2_id_at_vth_mA": mos2.id_at_vth_mA,
        "mos1_vth_interp": mos1.vth_interp,
        "mos2_vth_interp": mos2.vth_interp,
        "mos1_vth_interp_corr": corrected(mos1.vth_interp),
        "mos2_vth_interp_corr": corrected(mos2.vth_interp),
        "bcc_recv": bcc_recv,
        "bcc_calc": bcc_calc,
        "bcc_ok": bcc_ok,
        "cr_ok": cr_ok,
        "decoder_version": DECODER_VERSION,
    }

    iv_rows: list[dict] = []
    for mos_name, mos in (("MOS1", mos1), ("MOS2", mos2)):
        for index in range(N_POINTS):
            iv_rows.append(
                {
                    **metadata,
                    "frame_counter": frame[3],
                    "mos": mos_name,
                    "index": index,
                    "dac_code": int(mos.dac_code[index]),
                    "vgs": float(mos.vgs[index]),
                    "id_uA": float(mos.id_uA[index]),
                    "id_mA": float(mos.id_mA[index]),
                    "temp_degC": temp_degC,
                    "temp_coef_a": TEMP_COEF_A,
                    "vth": mos.vth,
                    "vth_corr": corrected(mos.vth),
                    "vth_interp": mos.vth_interp,
                    "vth_interp_corr": corrected(mos.vth_interp),
                    "bcc_ok": bcc_ok,
                    "cr_ok": cr_ok,
                    "decoder_version": DECODER_VERSION,
                }
            )
    return summary, iv_rows
