"""Deterministic synthetic provider for tests and examples."""

from datetime import datetime, timedelta
from math import pi, sin

from steppegrid.simulation.models import (
    DataProvenance,
    Location,
    WeatherDataset,
    WeatherSeries,
)


class SyntheticWeatherProvider:
    def get_hourly_weather(
        self, location: Location, start: datetime, end: datetime
    ) -> WeatherDataset:
        duration = end - start
        hours = int(duration.total_seconds() / 3600)
        if hours <= 0 or duration != timedelta(hours=hours):
            raise ValueError("synthetic weather period must contain positive whole hours")
        timestamps = [start + timedelta(hours=index) for index in range(hours)]
        irradiance = [
            max(0.0, 700.0 * sin(pi * (timestamp.hour - 6) / 12))
            for timestamp in timestamps
        ]
        wind = [4.0 + (index % 5) * 0.5 for index in range(hours)]
        temperature = [-5.0 + 5.0 * sin(2 * pi * timestamp.hour / 24) for timestamp in timestamps]
        return WeatherDataset(
            series=WeatherSeries(
                timestamps=timestamps,
                wind_speed_m_s=wind,
                solar_irradiance_w_m2=irradiance,
                temperature_c=temperature,
            ),
            provenance=DataProvenance(
                source="SteppeGrid deterministic synthetic weather generator",
                retrieved_at=None,
                latitude=location.latitude,
                longitude=location.longitude,
                start_time=start,
                end_time=end,
                original_units={
                    "wind_speed": "m/s",
                    "solar_irradiance": "W/m2",
                    "temperature": "degC",
                },
                normalized_units={
                    "wind_speed_m_s": "m/s",
                    "solar_irradiance_w_m2": "W/m2",
                    "temperature_c": "degC",
                },
                processing_notes=[
                    "Generated deterministically; not measured and not representative of the location."
                ],
            ),
        )
