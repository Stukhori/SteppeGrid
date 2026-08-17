"""Consistent interactive Altair charts and chart-ready data helpers."""

from __future__ import annotations

from datetime import timedelta
from typing import Mapping

import altair as alt
import pandas as pd

from steppegrid.app.theme import COLORS


def date_window(frame: pd.DataFrame, start, end) -> pd.DataFrame:
    dates = frame["timestamp"].dt.date
    return frame.loc[(dates >= start) & (dates <= end)].copy()


def monthly_energy(frame: pd.DataFrame, value: str) -> pd.DataFrame:
    indexed = frame.set_index("timestamp")
    result = indexed[value].resample("MS").sum().rename("energy_kwh").reset_index()
    result["month"] = result["timestamp"].dt.strftime("%b")
    return result[["month", "energy_kwh"]]


def line_chart(frame: pd.DataFrame, series: Mapping[str, tuple[str, str]], y_title: str, *, height: int = 290):
    columns = list(series)
    labels = {key: value[0] for key, value in series.items()}
    data = frame[["timestamp", *columns]].rename(columns=labels).melt("timestamp", var_name="Series", value_name="Value")
    return (
        alt.Chart(data).mark_line(strokeWidth=2).encode(
            x=alt.X("timestamp:T", title=None, axis=alt.Axis(format="%b %d", labelOverlap=True)),
            y=alt.Y("Value:Q", title=y_title, scale=alt.Scale(zero=False)),
            color=alt.Color("Series:N", scale=alt.Scale(domain=list(labels.values()), range=[series[key][1] for key in columns]), legend=alt.Legend(orient="top", title=None)),
            tooltip=[alt.Tooltip("timestamp:T", title="Time"), alt.Tooltip("Series:N"), alt.Tooltip("Value:Q", format=",.2f")],
        ).properties(height=height).interactive(bind_y=False)
    )


def area_chart(frame: pd.DataFrame, series: Mapping[str, tuple[str, str]], y_title: str, *, height: int = 220):
    columns = list(series)
    labels = {key: value[0] for key, value in series.items()}
    data = frame[["timestamp", *columns]].rename(columns=labels).melt("timestamp", var_name="Series", value_name="Value")
    return (
        alt.Chart(data).mark_area(opacity=.72).encode(
            x=alt.X("timestamp:T", title=None, axis=alt.Axis(format="%b %d", labelOverlap=True)),
            y=alt.Y("Value:Q", title=y_title),
            color=alt.Color("Series:N", scale=alt.Scale(domain=list(labels.values()), range=[series[key][1] for key in columns]), legend=alt.Legend(orient="top", title=None)),
            tooltip=[alt.Tooltip("timestamp:T", title="Time"), "Series:N", alt.Tooltip("Value:Q", format=",.2f")],
        ).properties(height=height).interactive(bind_y=False)
    )


def bar_chart(frame: pd.DataFrame, category: str, value: str, *, x_title: str | None = None, y_title: str | None = None, color: str = COLORS["primary"], height: int = 280):
    return (
        alt.Chart(frame).mark_bar(color=color, cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
            x=alt.X(f"{category}:N", title=x_title, sort=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y(f"{value}:Q", title=y_title),
            tooltip=[alt.Tooltip(f"{category}:N"), alt.Tooltip(f"{value}:Q", format=",.3f")],
        ).properties(height=height)
    )


def sensitivity_chart(frame: pd.DataFrame, target: float):
    scenarios = ["demand_low", "nominal", "demand_high", "pv_low", "pv_high", "wind_shear_low", "wind_shear_high", "resource_favorable", "resource_stress"]
    physical = frame.loc[frame["scenario"].isin(scenarios)].copy()
    physical["status"] = physical["passes_target"].map({True: "MEETS TARGET", False: "BELOW TARGET"})
    physical["served_percent"] = physical["served_fraction"] * 100
    bars = alt.Chart(physical).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X("scenario:N", title=None, sort=scenarios, axis=alt.Axis(labelAngle=-30)),
        y=alt.Y("served_percent:Q", title="Annual demand served (%)", scale=alt.Scale(zero=False)),
        color=alt.Color("status:N", scale=alt.Scale(domain=["MEETS TARGET", "BELOW TARGET"], range=[COLORS["success"], COLORS["critical"]]), legend=alt.Legend(orient="top", title=None)),
        tooltip=["scenario:N", "status:N", alt.Tooltip("served_percent:Q", title="Served", format=".3f"), "loss_of_load_hours:Q", "longest_deficit_hours:Q"],
    )
    threshold = pd.DataFrame({"threshold": [target * 100], "label": [f"{target:.0%} threshold"]})
    rule = alt.Chart(threshold).mark_rule(color=COLORS["text"], strokeDash=[6, 4], strokeWidth=2).encode(y="threshold:Q")
    label = alt.Chart(threshold).mark_text(align="right", dx=-5, dy=-7, color=COLORS["text"]).encode(y="threshold:Q", x=alt.value("width"), text="label:N")
    return (bars + rule + label).properties(height=330)


def wind_comparison(frame: pd.DataFrame, value: str, title: str, color: str = COLORS["wind"]):
    data = frame.copy(); data["equipment"] = data["model"]
    return bar_chart(data, "equipment", value, y_title=title, color=color, height=250)


def preset_dates(frame: pd.DataFrame, preset: str, events: pd.DataFrame | None = None):
    first, last = frame["timestamp"].iloc[0].date(), frame["timestamp"].iloc[-1].date()
    if preset == "First week": return first, min(first + timedelta(days=6), last)
    if preset == "Highest-curtailment week":
        date = frame.loc[frame["curtailment_kwh"].idxmax(), "timestamp"].date()
        return max(first, date - timedelta(days=3)), min(last, date + timedelta(days=3))
    if preset == "Longest deficit event" and events is not None and not events.empty:
        event = events.sort_values(["duration_hours", "unmet_energy_kwh"], ascending=False).iloc[0]
        return max(first, event["start"].date() - timedelta(days=1)), min(last, event["end"].date() + timedelta(days=1))
    return first, min(first + timedelta(days=6), last)
