from __future__ import annotations

import numpy as np


VTH_THRESHOLD_mA = 1.0


def calculate_vth(vgs: np.ndarray, id_mA: np.ndarray) -> tuple[float, int | None, float]:
    indices = np.flatnonzero(id_mA > VTH_THRESHOLD_mA)
    if len(indices) == 0:
        return np.nan, None, np.nan
    index = int(indices[0])
    return float(vgs[index]), index, float(id_mA[index])


def calculate_vth_interp(vgs: np.ndarray, id_mA: np.ndarray) -> float:
    indices = np.flatnonzero(id_mA > VTH_THRESHOLD_mA)
    if len(indices) == 0:
        return np.nan
    index = int(indices[0])
    if index == 0:
        return float(vgs[0])
    x0, x1 = float(vgs[index - 1]), float(vgs[index])
    y0, y1 = float(id_mA[index - 1]), float(id_mA[index])
    if y1 == y0:
        return x1
    return x0 + (VTH_THRESHOLD_mA - y0) * (x1 - x0) / (y1 - y0)
