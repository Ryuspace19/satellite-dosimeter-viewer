from __future__ import annotations

import math
import re

import numpy as np
import pandas as pd


A_GROUND = -0.003411429
T_REF = 25.0
SENSITIVITY_MV_PER_KRAD = 18.5
BIN_DAYS = 7
TARGET_COLUMNS = [
    "mos1_vth_interp", "mos2_vth_interp", "mos_mean_vth_interp",
    "mos1_vth25", "mos2_vth25", "mos_mean_vth25",
    "mos1_b_fixed", "mos2_b_fixed", "mos_mean_b_fixed",
    "mos1_minus_mos2_vth_mV", "mos1_minus_mos2_vth25_mV",
]


def _linregress(x: pd.Series, y: pd.Series) -> dict:
    valid = pd.DataFrame({"x": x, "y": y}).dropna()
    if len(valid) < 2 or valid["x"].nunique() < 2:
        return {"n": len(valid), "slope": np.nan, "intercept": np.nan, "r": np.nan, "r2": np.nan, "p_value": np.nan}
    try:
        from scipy.stats import linregress
        result = linregress(valid["x"], valid["y"])
        return {
            "n": len(valid), "slope": result.slope, "intercept": result.intercept,
            "r": result.rvalue, "r2": result.rvalue ** 2, "p_value": result.pvalue,
        }
    except ImportError:
        slope, intercept = np.polyfit(valid["x"], valid["y"], 1)
        r = np.corrcoef(valid["x"], valid["y"])[0, 1]
        return {"n": len(valid), "slope": slope, "intercept": intercept, "r": r, "r2": r ** 2, "p_value": np.nan}


def prepare_timeseries(summary: pd.DataFrame) -> pd.DataFrame:
    data = summary.copy()
    extracted = data["datetime_raw"].astype(str).str.extract(
        r"(?P<day>\d+)\s*日\s*(?P<hour>\d{1,2}):(?P<minute>\d{1,2}):(?P<second>\d{1,2})"
    )
    for column in extracted.columns:
        data[column] = pd.to_numeric(extracted[column], errors="coerce")
    data["seconds_in_day"] = data["hour"] * 3600 + data["minute"] * 60 + data["second"]
    data["elapsed_days_raw"] = data["day"] + data["seconds_in_day"] / 86400.0
    data = data.sort_values(["day", "seconds_in_day"], na_position="last").reset_index(drop=True)
    data["elapsed_days"] = data["elapsed_days_raw"] - data["elapsed_days_raw"].min()
    data["mos_mean_vth_interp"] = data[["mos1_vth_interp", "mos2_vth_interp"]].mean(axis=1)
    for prefix in ("mos1", "mos2", "mos_mean"):
        source = f"{prefix}_vth_interp"
        data[f"{prefix}_vth25"] = data[source] - A_GROUND * (data["temp_degC"] - T_REF)
        data[f"{prefix}_b_fixed"] = data[source] - A_GROUND * data["temp_degC"]
    data["mos1_minus_mos2_vth_mV"] = (data["mos1_vth_interp"] - data["mos2_vth_interp"]) * 1000
    data["mos1_minus_mos2_vth25_mV"] = (data["mos1_vth25"] - data["mos2_vth25"]) * 1000
    data["day_group"] = data["day"]
    data["week_group"] = np.floor(data["elapsed_days"] / 7)
    data["bin_group"] = np.floor(data["elapsed_days"] / BIN_DAYS)
    return data


def aggregate_statistics(data: pd.DataFrame, group_column: str) -> pd.DataFrame:
    grouped = data.groupby(group_column, dropna=True)[TARGET_COLUMNS].agg(
        ["count", "mean", "std", "sem", "min", "max", "median"]
    )
    grouped.columns = [
        f"{column}_{'n' if stat == 'count' else stat}" for column, stat in grouped.columns
    ]
    result = grouped.reset_index()
    elapsed = data.groupby(group_column)["elapsed_days"].agg(["min", "max", "mean"]).reset_index()
    elapsed.columns = [group_column, "elapsed_days_min", "elapsed_days_max", "elapsed_days_center"]
    return result.merge(elapsed, on=group_column, how="left")


def temperature_fits(data: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for target in ("mos1_vth_interp", "mos2_vth_interp", "mos_mean_vth_interp"):
        fit = _linregress(data["temp_degC"], data[target])
        rows.append(
            {
                "target": target,
                "n": fit["n"],
                "a_V_per_C": fit["slope"],
                "a_mV_per_C": fit["slope"] * 1000,
                "b_V": fit["intercept"],
                "r": fit["r"],
                "r2": fit["r2"],
                "p_value": fit["p_value"],
            }
        )
    return pd.DataFrame(rows)


def _change_judgement(change_mV: float) -> str:
    value = abs(change_mV)
    if math.isnan(value):
        return "判定不能"
    if value < 1:
        return "非常に小さい"
    if value < 3:
        return "慎重判断"
    if value < 5:
        return "候補"
    return "注目"


def time_trends(aggregate: pd.DataFrame) -> pd.DataFrame:
    rows = []
    targets = (
        "mos1_vth25_mean", "mos2_vth25_mean", "mos_mean_vth25_mean",
        "mos1_b_fixed_mean", "mos2_b_fixed_mean", "mos_mean_b_fixed_mean",
    )
    total_days = aggregate["elapsed_days_center"].max() - aggregate["elapsed_days_center"].min()
    for target in targets:
        fit = _linregress(aggregate["elapsed_days_center"], aggregate[target])
        slope_mV = fit["slope"] * 1000
        total_change = slope_mV * total_days
        rows.append(
            {
                "target": target,
                "n": fit["n"],
                "slope_mV_per_day": slope_mV,
                "estimated_total_change_mV": total_change,
                "estimated_total_change_rad_abs": abs(total_change) / SENSITIVITY_MV_PER_KRAD * 1000,
                "slope_rad_per_day_abs": abs(slope_mV) / SENSITIVITY_MV_PER_KRAD * 1000,
                "r": fit["r"],
                "r2": fit["r2"],
                "p_value": fit["p_value"],
                "significant_p_lt_0_05": bool(fit["p_value"] < 0.05) if pd.notna(fit["p_value"]) else False,
                "change_judgement": _change_judgement(total_change),
            }
        )
    return pd.DataFrame(rows)


def run_analysis(summary: pd.DataFrame) -> dict[str, pd.DataFrame]:
    timeseries = prepare_timeseries(summary)
    daily = aggregate_statistics(timeseries, "day_group")
    weekly = aggregate_statistics(timeseries, "week_group")
    binned = aggregate_statistics(timeseries, "bin_group")
    return {
        "timeseries": timeseries,
        "temperature_fits": temperature_fits(timeseries),
        "daily": daily,
        "weekly": weekly,
        "binned": binned,
        "time_trends": time_trends(binned),
    }
