"""Manual live compatibility check; this script is never run by pytest."""

from datetime import datetime, timezone

from steppegrid.simulation.models import Location
from steppegrid.weather.open_meteo import OpenMeteoHistoricalWeatherProvider


def main() -> None:
    provider = OpenMeteoHistoricalWeatherProvider()
    dataset = provider.get_hourly_weather(
        Location(name="Synthetic coordinate smoke test", latitude=50.0, longitude=51.0),
        datetime(2025, 1, 1, tzinfo=timezone.utc),
        datetime(2025, 1, 2, tzinfo=timezone.utc),
        refresh=True,
    )
    print(f"Fetched {len(dataset.series.timestamps)} ERA5 hours")
    print(dataset.provenance.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
