from __future__ import annotations

import numpy as np
import pandas as pd


VTH_CHARTS = [
    (["mos1_vth", "mos2_vth"], "MOS1/MOS2 Vth", "Vth [V]"),
    (["mos1_vth_corr", "mos2_vth_corr"], "MOS1/MOS2 Vth_corr", "Vth_corr [V]"),
    (
        ["mos1_vth_interp", "mos2_vth_interp"],
        "MOS1/MOS2 Vth_interp",
        "Vth_interp [V]",
    ),
    (["mos1_vth25", "mos2_vth25"], "MOS1/MOS2 Vth25", "Vth25 [V]"),
    (["mos_mean_vth25"], "MOS平均 Vth25", "Vth25 [V]"),
]


def calculate_day_rolling_means(
    data: pd.DataFrame,
    columns: list[str],
    windows_days: list[int],
) -> pd.DataFrame:
    """Add time-based rolling means using elapsed_days as the time axis."""
    result = data.copy()
    available = [column for column in columns if column in result.columns]
    if not available or "elapsed_days" not in result.columns:
        return result

    valid = result["elapsed_days"].notna()
    ordered = result.loc[valid].sort_values("elapsed_days")
    time_index = pd.to_timedelta(ordered["elapsed_days"], unit="D")
    values = ordered[available].copy()
    values.index = time_index

    for window_days in sorted(set(windows_days)):
        rolling = values.rolling(
            f"{window_days}D",
            min_periods=1,
            closed="both",
        ).mean()
        for column in available:
            output_column = f"{column}_{window_days}d_mean"
            result[output_column] = pd.NA
            result.loc[ordered.index, output_column] = rolling[column].to_numpy()
            result[output_column] = pd.to_numeric(
                result[output_column], errors="coerce"
            )
    return result


def calculate_linear_fit(
    elapsed_days: pd.Series,
    values: pd.Series,
) -> dict[str, float | int]:
    valid = pd.DataFrame(
        {
            "elapsed_days": pd.to_numeric(elapsed_days, errors="coerce"),
            "value": pd.to_numeric(values, errors="coerce"),
        }
    ).dropna()
    if len(valid) < 2 or valid["elapsed_days"].nunique() < 2:
        return {
            "n": len(valid),
            "slope_v_per_day": np.nan,
            "slope_mv_per_day": np.nan,
            "intercept_v": np.nan,
            "r2": np.nan,
        }

    slope, intercept = np.polyfit(valid["elapsed_days"], valid["value"], 1)
    predicted = slope * valid["elapsed_days"] + intercept
    residual_sum = float(((valid["value"] - predicted) ** 2).sum())
    total_sum = float(
        ((valid["value"] - valid["value"].mean()) ** 2).sum()
    )
    r2 = 1.0 - residual_sum / total_sum if total_sum > 0 else np.nan
    return {
        "n": len(valid),
        "slope_v_per_day": float(slope),
        "slope_mv_per_day": float(slope * 1000),
        "intercept_v": float(intercept),
        "r2": float(r2),
    }


def _fit_legend(series_name: str, fit: dict[str, float | int]) -> str:
    if pd.isna(fit["slope_mv_per_day"]):
        return f"{series_name} (一次近似不可)"
    return (
        f"{series_name} | 傾き {fit['slope_mv_per_day']:+.4f} mV/day"
        f" | 切片 {fit['intercept_v']:.6f} V"
        f" | R² {fit['r2']:.4f}"
    )


def _line_chart(
    st,
    px,
    data: pd.DataFrame,
    columns: list[str],
    title: str,
    y_title: str,
):
    available = [column for column in columns if column in data.columns]
    if not available:
        return
    plot = data[["elapsed_days", *available]].melt(
        id_vars="elapsed_days", var_name="series", value_name="value"
    )
    figure = px.line(plot, x="elapsed_days", y="value", color="series", title=title)
    figure.update_layout(xaxis_title="経過日数", yaxis_title=y_title)
    st.plotly_chart(figure, width="stretch")


def _vth_chart(
    st,
    px,
    data: pd.DataFrame,
    columns: list[str],
    title: str,
    y_title: str,
    windows_days: list[int],
):
    import plotly.graph_objects as go

    available = [column for column in columns if column in data.columns]
    if not available:
        return

    chart_data = calculate_day_rolling_means(data, available, windows_days)
    colors = px.colors.qualitative.Plotly
    figure = go.Figure()
    fit_rows: list[dict[str, float | int | str]] = []

    for column_index, column in enumerate(available):
        base_color = colors[column_index % len(colors)]
        figure.add_trace(
            go.Scatter(
                x=chart_data["elapsed_days"],
                y=chart_data[column],
                mode="lines",
                name=column,
                line={"color": base_color, "width": 1},
                opacity=0.3,
                legendgroup=column,
            )
        )

        for window_index, window_days in enumerate(windows_days):
            rolling_column = f"{column}_{window_days}d_mean"
            series_name = f"{column} ({window_days}日平均)"
            fit = calculate_linear_fit(
                chart_data["elapsed_days"], chart_data[rolling_column]
            )
            legend_name = _fit_legend(series_name, fit)
            fit_rows.append(
                {
                    "系列": column,
                    "移動平均": f"{window_days}日",
                    "データ数": fit["n"],
                    "傾き [mV/day]": fit["slope_mv_per_day"],
                    "切片 [V]": fit["intercept_v"],
                    "R²": fit["r2"],
                }
            )
            dash_styles = ["solid", "dash", "dot", "dashdot"]
            dash = dash_styles[window_index % len(dash_styles)]
            figure.add_trace(
                go.Scatter(
                    x=chart_data["elapsed_days"],
                    y=chart_data[rolling_column],
                    mode="lines",
                    name=legend_name,
                    line={"color": base_color, "width": 3, "dash": dash},
                    legendgroup=f"{column}_{window_days}",
                )
            )

            valid = pd.DataFrame(
                {
                    "x": pd.to_numeric(
                        chart_data["elapsed_days"], errors="coerce"
                    ),
                    "y": pd.to_numeric(
                        chart_data[rolling_column], errors="coerce"
                    ),
                }
            ).dropna()
            if len(valid) >= 2 and pd.notna(fit["slope_v_per_day"]):
                fit_x = np.array([valid["x"].min(), valid["x"].max()])
                fit_y = (
                    fit["slope_v_per_day"] * fit_x + fit["intercept_v"]
                )
                figure.add_trace(
                    go.Scatter(
                        x=fit_x,
                        y=fit_y,
                        mode="lines",
                        name=f"{series_name} 一次近似",
                        line={
                            "color": base_color,
                            "width": 2,
                            "dash": "dashdot",
                        },
                        opacity=0.75,
                        legendgroup=f"{column}_{window_days}",
                        showlegend=False,
                        hovertemplate=(
                            f"{series_name} 一次近似"
                            "<br>経過日数=%{x:.3f}"
                            "<br>Vth=%{y:.6f} V<extra></extra>"
                        ),
                    )
                )

    figure.update_layout(
        title=title,
        xaxis_title="経過日数",
        yaxis_title=y_title,
        legend_title="系列",
        hovermode="x unified",
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.18,
            "xanchor": "left",
            "x": 0,
            "font": {"size": 10},
        },
        margin={"b": 180},
    )
    st.plotly_chart(figure, width="stretch")
    if fit_rows:
        fit_table = pd.DataFrame(fit_rows)
        st.markdown("**一次近似結果**")
        st.dataframe(
            fit_table.style.format(
                {
                    "傾き [mV/day]": "{:+.6f}",
                    "切片 [V]": "{:.6f}",
                    "R²": "{:.5f}",
                },
                na_rep="-",
            ),
            width="stretch",
            hide_index=True,
        )


def render_dashboard(st, paths, status: dict, analyzed: pd.DataFrame):
    import plotly.express as px

    st.title("衛星線量計データビューア")
    st.caption(
        f"データ保存場所: {status.get('storage_location', paths.raw_dir)}"
    )
    manifest = status.get("manifest", {})
    st.write(f"最終読み込み日時: {manifest.get('last_loaded_at') or '未実行'}")

    cols = st.columns(5)
    cols[0].metric("rawファイル数", status.get("raw_file_count", 0))
    cols[1].metric("新規ファイル数", status.get("new_file_count", 0))
    cols[2].metric("更新ファイル数", status.get("updated_file_count", 0))
    cols[3].metric("復号成功数", status.get("decode_success_count", 0))
    cols[4].metric("復号失敗数", status.get("decode_failure_count", 0))
    cols = st.columns(3)
    cols[0].metric("復号エラー行数", status.get("row_error_count", 0))
    cols[1].metric("BCCエラー数", status.get("bcc_error_count", 0))
    cols[2].metric("CRエラー数", status.get("cr_error_count", 0))

    _render_downloads(st, paths)

    if analyzed.empty:
        st.info("グラフ表示用データがありません。")
        _render_processed_files(st, manifest)
        return

    st.header("温度データ")
    _line_chart(st, px, analyzed, ["temp_degC"], "温度の時系列", "温度 [degC]")

    st.header("Vthデータ")
    windows_days = st.multiselect(
        "Vth移動平均の期間",
        options=[1, 3, 7, 10, 14, 30],
        default=[3, 10],
        format_func=lambda value: f"{value}日間平均",
        help="観測行数ではなく、経過日数を基準に移動平均を計算します。",
    )
    for columns, title, y_title in VTH_CHARTS:
        _vth_chart(
            st,
            px,
            analyzed,
            columns,
            title,
            y_title,
            windows_days,
        )

    st.header("画像・特徴量データ")
    _line_chart(st, px, analyzed, ["feature_count"], "feature_count", "count")
    _line_chart(st, px, analyzed, ["sigma_dn"], "sigma_dn", "DN")
    _line_chart(st, px, analyzed, ["snr_db"], "snr_db", "dB")

    _render_processed_files(st, manifest)


def _combined_error_csv(paths) -> bytes | None:
    error_files = sorted(paths.decoded_dir.glob("*_decode_errors.csv"))
    frames = [
        pd.read_csv(path)
        for path in error_files
        if path.is_file() and path.stat().st_size > 0
    ]
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True).to_csv(
        index=False, encoding="utf-8-sig"
    ).encode("utf-8-sig")


def _render_downloads(st, paths) -> None:
    st.header("CSV・Excelを保存")
    st.caption(
        "現在選択中の読み込み元について、生成済みの解析結果を保存できます。"
    )
    downloads = [
        (
            "解析Excel",
            paths.reports_dir / "mosfet_analysis_results_ja.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        (
            "復号summary CSV",
            paths.graph_data_dir / "trend_master.csv",
            "text/csv",
        ),
        (
            "解析済み時系列 CSV",
            paths.graph_data_dir / "trend_master_analyzed.csv",
            "text/csv",
        ),
    ]
    error_csv = _combined_error_csv(paths)
    columns = st.columns(4)
    for index, (label, path, mime_type) in enumerate(downloads):
        exists = path.is_file()
        columns[index].download_button(
            label if exists else f"{label}（未生成）",
            data=path.read_bytes() if exists else b"",
            file_name=path.name,
            mime=mime_type,
            width="stretch",
            disabled=not exists,
        )
    columns[3].download_button(
        "復号エラー CSV" if error_csv is not None else "復号エラー CSV（なし）",
        data=error_csv or b"",
        file_name="decode_errors_all.csv",
        mime="text/csv",
        width="stretch",
        disabled=error_csv is None,
    )


def _render_processed_files(st, manifest: dict) -> None:
    processed = pd.DataFrame(manifest.get("processed_files", []))
    st.header("処理結果")
    st.subheader("処理済みファイル一覧")
    st.dataframe(processed, width="stretch", hide_index=True)
    st.subheader("エラーファイル一覧")
    if processed.empty:
        st.info("エラーはありません。")
        return
    error_items = processed[
        (processed.get("status", pd.Series(index=processed.index, dtype=str))
         == "failed")
        | processed.get(
            "error_file", pd.Series(index=processed.index, dtype=object)
        ).notna()
    ]
    if error_items.empty:
        st.info("エラーはありません。")
    else:
        st.dataframe(error_items, width="stretch", hide_index=True)
