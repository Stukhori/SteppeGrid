"""Diagnostic plots for Rodina resource-demand temporal alignment."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from statistics import fmean

from steppegrid.benchmarks.paired import PairedAnalysisResult


def _normalize(values: list[float]) -> list[float]:
    minimum, maximum = min(values), max(values)
    if maximum == minimum:
        return [0.0] * len(values)
    return [(value - minimum) / (maximum - minimum) for value in values]


def _week_plot(
    results: list[PairedAnalysisResult],
    start: datetime,
    path: Path,
    title: str,
    plt,
) -> None:
    end = start + timedelta(days=7)
    reference = results[0].aligned
    indices = [
        index
        for index, timestamp in enumerate(reference.timestamp_local)
        if start <= timestamp < end
    ]
    if len(indices) != 168:
        raise ValueError(f"representative week must contain 168 hours, received {len(indices)}")
    timestamps = [reference.timestamp_local[index] for index in indices]
    colors = ("#444444", "#b4473d", "#2f6f8f")
    figure, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    for result, color in zip(results, colors, strict=True):
        load = [result.aligned.total_load_kwh[index] for index in indices]
        axes[0].plot(
            timestamps,
            _normalize(load),
            color=color,
            linewidth=1.2,
            label=result.summary.shape,
        )
    axes[0].set_ylabel("Normalized load (0-1)")
    axes[0].set_ylim(-0.02, 1.05)
    axes[0].grid(alpha=0.25)
    axes[0].legend(ncol=3, fontsize=8)

    solar = [reference.solar_irradiance_w_m2[index] for index in indices]
    wind = [reference.wind_speed_m_s[index] for index in indices]
    axes[1].plot(
        timestamps,
        _normalize(solar),
        color="#d9a441",
        linewidth=1.2,
        label="Shortwave radiation",
    )
    axes[1].plot(
        timestamps,
        _normalize(wind),
        color="#3b8068",
        linewidth=1.2,
        label="ERA5 10 m wind speed",
    )
    axes[1].set_ylabel("Normalized resource (0-1)")
    axes[1].set_xlabel("Rodina local civil time (UTC+05:00)")
    axes[1].set_ylim(-0.02, 1.05)
    axes[1].grid(alpha=0.25)
    axes[1].legend(ncol=2, fontsize=8)
    figure.suptitle(title + " (each series independently normalized)")
    figure.autofmt_xdate()
    figure.tight_layout()
    figure.savefig(path, dpi=180, metadata={"Title": title})
    plt.close(figure)


def create_paired_plots(
    results: list[PairedAnalysisResult], output_directory: str | Path
) -> list[Path]:
    if len(results) != 3:
        raise ValueError("paired plots require all three Rodina load assumptions")
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as error:
        raise RuntimeError(
            'Rodina paired plots require: python -m pip install -e ".[visualization]"'
        ) from error

    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    reference = results[0]
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    figure, axis = plt.subplots(figsize=(10, 5.8))
    axis.plot(
        months,
        [row.normalized_load for row in reference.monthly],
        color="#444444",
        marker="o",
        label="Published monthly-row load",
    )
    axis.plot(
        months,
        [row.normalized_solar_irradiation for row in reference.monthly],
        color="#d9a441",
        marker="s",
        label="Horizontal irradiation",
    )
    axis.plot(
        months,
        [row.normalized_mean_wind for row in reference.monthly],
        color="#3b8068",
        marker="^",
        label="ERA5 10 m mean wind speed",
    )
    axis.set_title("Rodina monthly load and resource seasonality")
    axis.set_xlabel("Local calendar month")
    axis.set_ylabel("Independent min-max normalization (0-1)")
    axis.set_ylim(-0.02, 1.05)
    axis.grid(alpha=0.25)
    axis.legend()
    figure.tight_layout()
    monthly_path = output / "monthly_resource_load.png"
    figure.savefig(
        monthly_path,
        dpi=180,
        metadata={"Title": "Rodina normalized monthly load-resource seasonality"},
    )
    plt.close(figure)
    paths.append(monthly_path)

    local_timezone = reference.aligned.timestamp_local[0].tzinfo
    year = reference.summary.reference_year
    assert local_timezone is not None
    winter_path = output / "winter_week.png"
    _week_plot(
        results,
        datetime(year, 1, 13, tzinfo=local_timezone),
        winter_path,
        "Representative winter week",
        plt,
    )
    paths.append(winter_path)
    summer_path = output / "summer_week.png"
    _week_plot(
        results,
        datetime(year, 7, 14, tzinfo=local_timezone),
        summer_path,
        "Representative summer week",
        plt,
    )
    paths.append(summer_path)

    hours = list(range(24))
    figure, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    colors = ("#444444", "#b4473d", "#2f6f8f")
    for result, color in zip(results, colors, strict=True):
        typical_load = [
            fmean(
                value
                for timestamp, value in zip(
                    result.aligned.timestamp_local,
                    result.aligned.total_load_kwh,
                    strict=True,
                )
                if timestamp.hour == hour
            )
            for hour in hours
        ]
        axes[0].plot(
            hours,
            typical_load,
            color=color,
            marker="o",
            label=result.summary.shape,
        )
    axes[0].set_ylabel("Mean load (kWh/hour)")
    axes[0].grid(alpha=0.25)
    axes[0].legend(ncol=3, fontsize=8)

    typical_solar = [
        fmean(
            value
            for timestamp, value in zip(
                reference.aligned.timestamp_local,
                reference.aligned.solar_irradiance_w_m2,
                strict=True,
            )
            if timestamp.hour == hour
        )
        for hour in hours
    ]
    typical_wind = [
        fmean(
            value
            for timestamp, value in zip(
                reference.aligned.timestamp_local,
                reference.aligned.wind_speed_m_s,
                strict=True,
            )
            if timestamp.hour == hour
        )
        for hour in hours
    ]
    axes[1].plot(
        hours,
        _normalize(typical_solar),
        color="#d9a441",
        marker="s",
        label="Shortwave radiation",
    )
    axes[1].plot(
        hours,
        _normalize(typical_wind),
        color="#3b8068",
        marker="^",
        label="ERA5 10 m wind speed",
    )
    axes[1].set_xlabel("Rodina local hour of day (UTC+05:00)")
    axes[1].set_ylabel("Normalized resource (0-1)")
    axes[1].set_xticks(hours)
    axes[1].grid(alpha=0.25)
    axes[1].legend(ncol=2, fontsize=8)
    figure.suptitle("Typical local-day load and resource timing")
    figure.tight_layout()
    typical_day_path = output / "typical_day_comparison.png"
    figure.savefig(
        typical_day_path,
        dpi=180,
        metadata={"Title": "Rodina typical local-day timing comparison"},
    )
    plt.close(figure)
    paths.append(typical_day_path)
    return paths
