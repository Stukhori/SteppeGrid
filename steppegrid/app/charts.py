"""Data-frame shaping for Streamlit charts."""

from __future__ import annotations

import pandas as pd


def date_window(frame: pd.DataFrame, start, end) -> pd.DataFrame:
    dates = frame["timestamp"].dt.date
    return frame.loc[(dates >= start) & (dates <= end)].copy()


def monthly_energy(frame: pd.DataFrame, value: str) -> pd.DataFrame:
    indexed = frame.set_index("timestamp")
    result = indexed[value].resample("MS").sum().rename("energy_kwh").reset_index()
    result["month"] = result["timestamp"].dt.strftime("%b")
    return result[["month", "energy_kwh"]]
