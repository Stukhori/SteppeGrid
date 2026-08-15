import csv
from datetime import datetime, timezone
from pathlib import Path

from steppegrid.export import RESULT_COLUMNS, export_hourly_results_csv
from steppegrid.scenario import load_and_resolve_scenario
from steppegrid.simulation.models import Location
from steppegrid.simulation.simulator import simulate
from steppegrid.weather.csv_provider import CSVWeatherProvider


SCENARIO_PATH = Path("examples/scenarios/synthetic_household.yaml")


def test_synthetic_scenario_is_reproducible():
    first = simulate(load_and_resolve_scenario(SCENARIO_PATH).simulation_input)
    second = simulate(load_and_resolve_scenario(SCENARIO_PATH).simulation_input)
    assert first == second


def test_csv_weather_to_simulation_to_result_csv_round_trip(tmp_path, scenario_factory):
    weather_path = tmp_path / "weather.csv"
    weather_path.write_text(
        "timestamp,wind_speed_m_s,solar_irradiance_w_m2,temperature_c\n"
        "2026-01-01T00:00:00+00:00,0,1000,-10\n"
        "2026-01-01T01:00:00+00:00,0,0,-11\n",
        encoding="utf-8",
    )
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    weather = CSVWeatherProvider(weather_path, source="test fixture").get_hourly_weather(
        Location(latitude=50, longitude=70),
        start,
        datetime(2026, 1, 1, 2, tzinfo=timezone.utc),
    )
    inputs = scenario_factory(hours=2, solar_capacity_kw=1).model_copy(
        update={"weather": weather.series}
    )
    result = simulate(inputs)
    output = tmp_path / "hourly.csv"
    export_hourly_results_csv(result, output)
    with output.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert tuple(rows[0]) == RESULT_COLUMNS
    assert len(rows) == 2
    assert float(rows[0]["demand_kwh"]) == 1.0
    assert rows[0]["timestamp"] == result.hourly[0].timestamp.isoformat()


def test_scenario_json_serialization_round_trip():
    scenario = load_and_resolve_scenario(SCENARIO_PATH).scenario
    assert scenario.model_validate_json(scenario.model_dump_json()) == scenario
