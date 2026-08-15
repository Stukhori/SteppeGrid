"""Research diagnostic plots for pilot-site weather analysis."""

from __future__ import annotations

from pathlib import Path

from steppegrid.site.analysis import PilotSiteAnalysis
from steppegrid.simulation.models import WeatherDataset


def create_site_plots(
    dataset: WeatherDataset, analysis: PilotSiteAnalysis, output_directory: Path
) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as error:
        raise RuntimeError(
            'Pilot-site plots require: python -m pip install -e ".[visualization]"'
        ) from error

    output_directory.mkdir(parents=True, exist_ok=True)
    wind = dataset.series.wind_speed_m_s
    months = [row.month_name[:3] for row in analysis.monthly]

    figure, axis = plt.subplots(figsize=(9, 5.5))
    upper = max(10, int(max(wind)) + 2)
    axis.hist(wind, bins=range(0, upper + 1), color="#2f6f8f", edgecolor="white")
    axis.set_title("Distribution of hourly ERA5 10 m wind speed")
    axis.set_xlabel("ERA5 10 m wind speed (m/s)")
    axis.set_ylabel("Hourly records")
    axis.set_xlim(left=0)
    axis.grid(axis="y", alpha=0.25)
    figure.tight_layout()
    figure.savefig(output_directory / "wind_distribution.png", dpi=180, metadata={"Title": "ERA5 10 m wind distribution"})
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(9, 5.5))
    means = [row.mean_wind_speed_10m_m_s for row in analysis.monthly]
    medians = [row.median_wind_speed_10m_m_s for row in analysis.monthly]
    axis.bar(months, means, color="#2f6f8f", label="Monthly mean")
    axis.plot(months, medians, color="#b4473d", marker="o", label="Monthly median")
    axis.set_title("Monthly ERA5 10 m wind speed")
    axis.set_xlabel("Month")
    axis.set_ylabel("Wind speed (m/s)")
    axis.set_ylim(bottom=0)
    axis.grid(axis="y", alpha=0.25)
    axis.legend()
    figure.tight_layout()
    figure.savefig(output_directory / "monthly_wind.png", dpi=180, metadata={"Title": "Monthly ERA5 10 m wind"})
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(9, 5.5))
    irradiation = [row.horizontal_irradiation_kwh_m2 for row in analysis.monthly]
    axis.bar(months, irradiation, color="#d9a441")
    axis.set_title("Monthly ERA5 horizontal shortwave irradiation")
    axis.set_xlabel("Month")
    axis.set_ylabel("Horizontal irradiation (kWh/m2)")
    axis.set_ylim(bottom=0)
    axis.grid(axis="y", alpha=0.25)
    figure.tight_layout()
    figure.savefig(output_directory / "monthly_solar.png", dpi=180, metadata={"Title": "Monthly horizontal irradiation"})
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(9, 5.5))
    axis.plot(
        months,
        [row.normalized_mean_wind for row in analysis.monthly],
        color="#2f6f8f",
        marker="o",
        label="Normalized monthly mean ERA5 10 m wind",
    )
    axis.plot(
        months,
        [row.normalized_solar_irradiation for row in analysis.monthly],
        color="#d9a441",
        marker="s",
        label="Normalized monthly horizontal irradiation",
    )
    axis.set_title("Monthly wind and solar seasonality (independently normalized)")
    axis.set_xlabel("Month")
    axis.set_ylabel("Normalized resource (0-1)")
    axis.set_ylim(0, 1.05)
    axis.grid(alpha=0.25)
    axis.legend()
    figure.tight_layout()
    figure.savefig(
        output_directory / "wind_solar_seasonality.png",
        dpi=180,
        metadata={"Title": "Normalized wind and solar seasonality"},
    )
    plt.close(figure)
