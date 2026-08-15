"""Conservative Markdown reporting for pilot-site resource analysis."""

from steppegrid.site.analysis import PilotSiteAnalysis
from steppegrid.site.config import PilotSiteConfig
from steppegrid.simulation.models import DataProvenance


def render_site_report(
    config: PilotSiteConfig,
    analysis: PilotSiteAnalysis,
    provenance: DataProvenance,
) -> str:
    strongest_wind = max(analysis.monthly, key=lambda row: row.mean_wind_speed_10m_m_s)
    weakest_wind = min(analysis.monthly, key=lambda row: row.mean_wind_speed_10m_m_s)
    correlation = (
        f"{analysis.monthly_wind_solar_correlation:.3f}"
        if analysis.monthly_wind_solar_correlation is not None
        else "undefined because one monthly series is constant"
    )
    district = getattr(config.site, "district", None)
    region = getattr(config.site, "region", None)
    administrative_lines = "\n".join(
        line
        for line in (
            f"- District: {district}" if district else "",
            f"- Region: {region}" if region else "",
        )
        if line
    )
    coordinate_distance = (
        f"{provenance.coordinate_distance_km:.3f} km"
        if provenance.coordinate_distance_km is not None
        else "not recorded"
    )
    monthly_rows = "\n".join(
        "| "
        f"{row.month_name} | {row.records} | {row.mean_wind_speed_10m_m_s:.3f} | "
        f"{row.median_wind_speed_10m_m_s:.3f} | "
        f"{row.mean_shortwave_irradiance_w_m2:.3f} | "
        f"{row.horizontal_irradiation_kwh_m2:.3f} | {row.mean_temperature_c:.3f} |"
        for row in analysis.monthly
    )
    return f"""# Pilot Site Weather and Resource Report

## Pilot Site

- Name: {config.site.name}
{administrative_lines}
- Requested coordinates: {config.site.latitude}, {config.site.longitude}
- Returned grid coordinates: {provenance.returned_latitude}, {provenance.returned_longitude}
- Approximate requested-to-grid distance: {coordinate_distance}
- Country: {config.site.country}
- Weather source: {provenance.provider}
- Underlying model: {provenance.underlying_model}
- Timezone: {provenance.timezone}
- Wind variable: ERA5 10 m wind speed (`wind_speed_10m`)
- Solar variable: ERA5 shortwave radiation (`shortwave_radiation`), hourly mean in W/m2
- Analysis period: {config.weather.start_date.isoformat()} to {config.weather.end_date.isoformat()} (end exclusive)
- Retrieval time: {provenance.retrieved_at.isoformat() if provenance.retrieved_at else 'not recorded'}
- Cache key: {provenance.cache_key}

## Data Quality

### Data

- Expected hourly records: {analysis.data_quality.expected_records}
- Received hourly records: {analysis.data_quality.received_records}
- Missing timestamps: {analysis.data_quality.missing_timestamps}
- Duplicate timestamps: {analysis.data_quality.duplicate_timestamps}
- Missing required values: {analysis.data_quality.missing_required_values}
- Chronology: consecutive UTC hours

## Wind Resource

### Calculated Statistics

All wind statistics describe **ERA5 10 m wind speed**, not turbine hub-height wind.

- Annual mean: {analysis.wind.mean_m_s:.3f} m/s
- Annual median: {analysis.wind.median_m_s:.3f} m/s
- Standard deviation: {analysis.wind.standard_deviation_m_s:.3f} m/s
- 5th / 25th / 75th / 95th percentiles: {analysis.wind.percentile_5_m_s:.3f} / {analysis.wind.percentile_25_m_s:.3f} / {analysis.wind.percentile_75_m_s:.3f} / {analysis.wind.percentile_95_m_s:.3f} m/s
- Maximum: {analysis.wind.maximum_m_s:.3f} m/s
- Hours below 2 m/s: {analysis.wind.percent_below_2_m_s:.2f}%
- Hours from 2 to below 3 m/s: {analysis.wind.percent_2_to_3_m_s:.2f}%
- Hours from 3 to below 5 m/s: {analysis.wind.percent_3_to_5_m_s:.2f}%
- Hours from 5 through 8 m/s: {analysis.wind.percent_5_to_8_m_s:.2f}%
- Hours above 8 m/s: {analysis.wind.percent_above_8_m_s:.2f}%
- Strongest monthly mean: {strongest_wind.month_name} ({strongest_wind.mean_wind_speed_10m_m_s:.3f} m/s)
- Weakest monthly mean: {weakest_wind.month_name} ({weakest_wind.mean_wind_speed_10m_m_s:.3f} m/s)

These speed bands are descriptive and are not turbine cut-in categories.

## Solar Resource

### Calculated Statistics

- Annual mean shortwave irradiance: {analysis.solar.annual_mean_irradiance_w_m2:.3f} W/m2
- Annual horizontal irradiation: {analysis.solar.annual_horizontal_irradiation_kwh_m2:.3f} kWh/m2
- Highest monthly irradiation: {analysis.solar.highest_irradiation_month}
- Lowest monthly irradiation: {analysis.solar.lowest_irradiation_month}

Monthly irradiation integrates each preceding-hour mean irradiance over one hour before converting Wh/m2 to kWh/m2.

## Temperature

- Annual mean: {analysis.temperature.annual_mean_c:.3f} degC
- Minimum: {analysis.temperature.minimum_c:.3f} degC
- Maximum: {analysis.temperature.maximum_c:.3f} degC

Temperature is included as site context; the current PV equation does not use it.

## Monthly Resource Summary

| Month | Records | Mean ERA5 10 m wind (m/s) | Median ERA5 10 m wind (m/s) | Mean shortwave irradiance (W/m2) | Horizontal irradiation (kWh/m2) | Mean temperature (degC) |
|---|---:|---:|---:|---:|---:|---:|
{monthly_rows}

## Wind-Solar Seasonal Relationship

### Calculated Statistic

The Pearson correlation between the 12 monthly mean ERA5 10 m wind speeds and the 12 monthly horizontal irradiation totals is {correlation}.

### Interpretation

The normalized seasonality plot supports visual comparison of monthly patterns. Correlation and visual opposition do not establish system-level complementarity or outage resilience; those require the energy simulation with an explicit load and storage scenario.

## Scientific Limitations

- ERA5 is gridded reanalysis, not a measured village weather-station record.
- ERA5 has approximately 0.25-degree dataset resolution, so local terrain and building effects are unresolved.
- Wind is at 10 m; no terrain or turbine hub-height correction is applied.
- No measured village weather station is integrated.
- The simple PV model does not explicitly model tilt, azimuth, snow, shading, degradation, or detailed inverter and temperature losses.
- This report is descriptive and makes no equipment or installation recommendation.

## Next Step

Use the generated `simulation_weather_reference.yaml` to build controlled grid-only, solar, wind, and hybrid scenarios for the same site and weather year. Equipment sizing and optimization remain outside this report.
"""
