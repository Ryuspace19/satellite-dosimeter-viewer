from __future__ import annotations

from io import BytesIO
from pathlib import Path
import re

import pandas as pd


ENCODINGS = ("utf-8-sig", "cp932", "shift_jis", "utf-8", "latin1")
COLUMN_MAP = {
    "カウンタ": "internal_counter",
    "蓄積時刻": "datetime_raw",
    "ログ": "raw_data",
}
CANONICAL_COLUMNS = ["internal_counter", "datetime_raw", "raw_data"]


def read_raw_csv(path: Path) -> pd.DataFrame:
    raw = Path(path).read_bytes()
    errors: list[str] = []
    for encoding in ENCODINGS:
        try:
            text = raw.decode(encoding)
        except UnicodeDecodeError as exc:
            errors.append(f"{encoding}: {exc}")
            continue
        for separator in (None, ",", "\t"):
            try:
                kwargs = {"sep": separator}
                if separator is None:
                    kwargs["engine"] = "python"
                frame = pd.read_csv(BytesIO(text.encode("utf-8")), encoding="utf-8", **kwargs)
                if frame.shape[1] < 3:
                    continue
                frame = frame.iloc[:, :3].copy()
                renamed = [COLUMN_MAP.get(str(column).strip(), str(column).strip()) for column in frame.columns]
                frame.columns = renamed
                if not set(CANONICAL_COLUMNS).issubset(frame.columns):
                    frame.columns = CANONICAL_COLUMNS
                frame = frame[CANONICAL_COLUMNS]
                frame["raw_data"] = frame["raw_data"].astype("string").str.strip()
                frame = frame[
                    frame["raw_data"].notna()
                    & (frame["raw_data"] != "")
                    & (frame["raw_data"].str.lower() != "nan")
                ].copy()
                return frame.reset_index(drop=True)
            except Exception as exc:
                errors.append(f"{encoding}/{separator!r}: {exc}")
    raise ValueError(f"CSV/TSVを読み込めませんでした: {'; '.join(errors[-5:])}")


def raw_string_to_bytes(raw_data: object) -> bytes:
    text = re.sub(r"[\s\r\n\t]+", "", str(raw_data))
    if text.upper().startswith("RS"):
        hex_text = re.sub(r"[^0-9A-Fa-f]", "", text[2:])
        prefix = b"RS"
    else:
        hex_text = re.sub(r"[^0-9A-Fa-f]", "", text)
        prefix = b""
    if len(hex_text) % 2:
        raise ValueError("16進数文字数が奇数です")
    try:
        frame = prefix + bytes.fromhex(hex_text)
    except ValueError as exc:
        raise ValueError(f"16進数の変換に失敗しました: {exc}") from exc
    if len(frame) == 252:
        frame += b"\x0d"
    if len(frame) != 253:
        raise ValueError(f"フレーム長が不正です: {len(frame)} byte")
    if frame[:2] != b"RS":
        raise ValueError("フレームヘッダーがRSではありません")
    return frame
