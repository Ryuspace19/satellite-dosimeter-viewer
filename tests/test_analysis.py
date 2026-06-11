from pathlib import Path

import pandas as pd

from app.analysis.orbit_analysis import run_analysis
from app.decoder.service import decode_file
from app.ui.dashboard import calculate_day_rolling_means, calculate_linear_fit


SAMPLE = Path(r"C:\Users\ryuai\Desktop\線量計application\生データ\DmuLog_20260530_153111.csv")


def test_analysis_computes_vth25_and_groups():
    summary, _, _ = decode_file(SAMPLE)
    results = run_analysis(summary)
    timeseries = results["timeseries"]
    assert "mos1_vth25" in timeseries
    assert "mos_mean_vth25" in timeseries
    assert not results["daily"].empty
    assert list(results["temperature_fits"]["target"]) == [
        "mos1_vth_interp", "mos2_vth_interp", "mos_mean_vth_interp"
    ]


def test_day_rolling_mean_uses_elapsed_time():
    data = pd.DataFrame(
        {
            "elapsed_days": [0.0, 1.0, 4.0, 10.0],
            "mos1_vth": [1.0, 3.0, 9.0, 20.0],
        }
    )
    result = calculate_day_rolling_means(data, ["mos1_vth"], [3, 10])
    assert result.loc[2, "mos1_vth_3d_mean"] == 6.0
    assert result.loc[3, "mos1_vth_3d_mean"] == 20.0
    assert result.loc[3, "mos1_vth_10d_mean"] == 8.25


def test_linear_fit_returns_slope_intercept_and_r2():
    fit = calculate_linear_fit(
        pd.Series([0.0, 1.0, 2.0, 3.0]),
        pd.Series([1.0, 1.002, 1.004, 1.006]),
    )
    assert abs(fit["slope_mv_per_day"] - 2.0) < 1e-9
    assert abs(fit["intercept_v"] - 1.0) < 1e-9
    assert abs(fit["r2"] - 1.0) < 1e-9
