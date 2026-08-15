"""Weather-provider contract consumed by scenario construction, not simulation."""

from datetime import datetime
from typing import Protocol

from steppegrid.simulation.models import Location, WeatherDataset


class WeatherProvider(Protocol):
    def get_hourly_weather(
        self, location: Location, start: datetime, end: datetime
    ) -> WeatherDataset:
        """Return normalized observations for [start, end)."""
        ...
