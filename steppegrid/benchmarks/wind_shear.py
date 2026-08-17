"""Robust two-height ERA5 wind-shear diagnostics for controlled benchmarks."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import datetime
from statistics import correlation, fmean, median

MINIMUM_SHEAR_WIND_SPEED_M_S = 0.5
GENERIC_SHEAR_EXPONENT = 1 / 7


@dataclass(frozen=True)
class ShearEstimate:
    exponent: float
    total_pairs: int
    valid_pairs: int
    excluded_near_zero_pairs: int
    excluded_nonfinite_pairs: int
    pairs_100m_not_above_10m: int
    mean_hourly_exponent: float
    median_hourly_exponent: float
    percentile_5: float
    percentile_25: float
    percentile_75: float
    percentile_95: float
    minimum_hourly_exponent: float
    maximum_hourly_exponent: float
    minimum_wind_speed_m_s: float
    monthly_median_exponents: list[float | None]
    terminology: str = "ERA5-derived Rodina 2025 two-height shear exponent; not site-measured shear"

    def to_dict(self) -> dict:
        return asdict(self)


def _percentile(sorted_values: list[float], percentile: float) -> float:
    position=(len(sorted_values)-1)*percentile
    lower=math.floor(position); upper=math.ceil(position)
    if lower==upper: return sorted_values[lower]
    fraction=position-lower
    return sorted_values[lower]*(1-fraction)+sorted_values[upper]*fraction


def estimate_two_height_shear(wind_speed_10m_m_s, wind_speed_100m_m_s, *,
    timestamps: list[datetime] | None = None,
    minimum_wind_speed_m_s: float = MINIMUM_SHEAR_WIND_SPEED_M_S) -> ShearEstimate:
    """Return median log-ratio alpha; retain negative shear when both speeds are stable."""
    if len(wind_speed_10m_m_s)!=len(wind_speed_100m_m_s):
        raise ValueError("10 m and 100 m wind arrays must have equal lengths")
    if timestamps is not None and len(timestamps)!=len(wind_speed_10m_m_s):
        raise ValueError("timestamps and wind arrays must have equal lengths")
    if minimum_wind_speed_m_s<=0:
        raise ValueError("minimum_wind_speed_m_s must be positive")
    valid=[]; monthly=[[] for _ in range(12)]; near_zero=nonfinite=not_above=0
    for index,(v10,v100) in enumerate(zip(wind_speed_10m_m_s,wind_speed_100m_m_s,strict=True)):
        if not math.isfinite(v10) or not math.isfinite(v100):
            nonfinite+=1; continue
        if v100<=v10: not_above+=1
        if v10<minimum_wind_speed_m_s or v100<minimum_wind_speed_m_s:
            near_zero+=1; continue
        alpha=math.log(v100/v10)/math.log(10)
        valid.append(alpha)
        if timestamps is not None: monthly[timestamps[index].month-1].append(alpha)
    if len(valid)<2:
        raise ValueError("at least two valid paired wind observations are required")
    ordered=sorted(valid); med=median(ordered)
    return ShearEstimate(exponent=med,total_pairs=len(wind_speed_10m_m_s),valid_pairs=len(valid),
        excluded_near_zero_pairs=near_zero,excluded_nonfinite_pairs=nonfinite,
        pairs_100m_not_above_10m=not_above,mean_hourly_exponent=fmean(valid),
        median_hourly_exponent=med,percentile_5=_percentile(ordered,.05),
        percentile_25=_percentile(ordered,.25),percentile_75=_percentile(ordered,.75),
        percentile_95=_percentile(ordered,.95),minimum_hourly_exponent=ordered[0],
        maximum_hourly_exponent=ordered[-1],minimum_wind_speed_m_s=minimum_wind_speed_m_s,
        monthly_median_exponents=[median(values) if values else None for values in monthly])


def reconstruct_10m_diagnostics(actual_10m, wind_100m, exponent: float) -> dict:
    if len(actual_10m)!=len(wind_100m) or not actual_10m:
        raise ValueError("equal non-empty wind arrays are required")
    reconstructed=[v*(10/100)**exponent for v in wind_100m]
    errors=[r-a for r,a in zip(reconstructed,actual_10m,strict=True)]
    return {"exponent":exponent,"mean_actual_10m_m_s":fmean(actual_10m),
        "mean_reconstructed_10m_m_s":fmean(reconstructed),"mean_bias_m_s":fmean(errors),
        "mae_m_s":fmean(abs(v) for v in errors),
        "rmse_m_s":math.sqrt(fmean(v*v for v in errors)),
        "pearson_correlation":correlation(actual_10m,reconstructed) if len(set(actual_10m))>1 and len(set(reconstructed))>1 else None}
