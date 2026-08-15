from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from steppegrid.load.csv_provider import CSVLoadProvider, LoadDataError
from steppegrid.load.synthetic import SyntheticLoadProvider
from steppegrid.simulation.models import LoadDataQuality, LoadProfile, SimulationInput


START = datetime(2025, 1, 1, tzinfo=timezone.utc)


def _write_load_csv(path, rows: list[str], *, critical: bool = True) -> None:
    header = "timestamp,total_load_kwh,critical_load_kwh\n" if critical else (
        "timestamp,total_load_kwh\n"
    )
    path.write_text(header + "\n".join(rows) + "\n", encoding="utf-8")


def test_valid_hourly_csv_with_explicit_critical_load(tmp_path):
    path = tmp_path / "load.csv"
    _write_load_csv(
        path,
        [
            "2025-01-01T00:00:00Z,0.72,0.21",
            "2025-01-01T01:00:00Z,0.64,0.19",
        ],
    )
    dataset = CSVLoadProvider(
        path, data_quality=LoadDataQuality.MEASURED
    ).get_hourly_load(START, START + timedelta(hours=2))
    assert dataset.total_load_kwh == [0.72, 0.64]
    assert dataset.critical_load_kwh == [0.21, 0.19]
    assert dataset.provenance.data_quality is LoadDataQuality.MEASURED


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        (["2025-01-01T00:00:00Z,-1,0"], "finite and non-negative"),
        (
            ["2025-01-01T00:00:00Z,1,0", "2025-01-01T02:00:00Z,1,0"],
            "missing or non-hourly",
        ),
        (
            ["2025-01-01T00:00:00Z,1,0", "2025-01-01T00:00:00Z,1,0"],
            "duplicate",
        ),
        (["2025-01-01T00:00:00Z,,0"], "missing load value"),
        (["2025-01-01T00:00:00Z,1,1.1"], "cannot exceed"),
    ],
)
def test_invalid_csv_load_is_rejected(tmp_path, rows, message):
    path = tmp_path / "load.csv"
    _write_load_csv(path, rows)
    with pytest.raises(LoadDataError, match=message):
        CSVLoadProvider(path).read()


def test_csv_rejects_timezone_naive_and_mixed_offsets(tmp_path):
    naive = tmp_path / "naive.csv"
    _write_load_csv(naive, ["2025-01-01T00:00:00,1"], critical=False)
    with pytest.raises(LoadDataError, match="UTC offset"):
        CSVLoadProvider(naive).read()

    mixed = tmp_path / "mixed.csv"
    _write_load_csv(
        mixed,
        [
            "2025-01-01T00:00:00+00:00,1",
            "2025-01-01T02:00:00+01:00,1",
        ],
        critical=False,
    )
    with pytest.raises(LoadDataError, match="consistent UTC offset"):
        CSVLoadProvider(mixed).read()


def test_csv_rejects_critical_fraction_with_explicit_critical_series(tmp_path):
    path = tmp_path / "load.csv"
    _write_load_csv(path, ["2025-01-01T00:00:00Z,1,0.4"])
    with pytest.raises(LoadDataError, match="cannot be combined"):
        CSVLoadProvider(path, critical_fraction=0.5).read()


def test_target_annual_scaling_integrates_to_requested_energy():
    dataset = SyntheticLoadProvider(
        profile="residential_like", target_annual_kwh=5000
    ).get_hourly_load(START, datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert sum(dataset.total_load_kwh) == pytest.approx(5000)
    assert dataset.provenance.scaling_factor == pytest.approx(
        5000 / sum(
            SyntheticLoadProvider(profile="residential_like")
            .get_hourly_load(START, datetime(2026, 1, 1, tzinfo=timezone.utc))
            .total_load_kwh
        )
    )


def test_target_annual_scaling_rejects_partial_year():
    with pytest.raises(ValueError, match="complete calendar year"):
        SyntheticLoadProvider(target_annual_kwh=100).get_hourly_load(
            START, START + timedelta(hours=24)
        )


def test_critical_fraction_is_explicit_and_reproducible():
    provider = SyntheticLoadProvider(
        profile="community_facility_like", critical_fraction=0.3, scale_factor=2
    )
    first = provider.get_hourly_load(START, START + timedelta(hours=48))
    second = provider.get_hourly_load(START, START + timedelta(hours=48))
    assert first == second
    assert first.critical_load_kwh == pytest.approx(
        [value * 0.3 for value in first.total_load_kwh]
    )
    assert "Assumed constant critical fraction" in (
        first.provenance.critical_load_method or ""
    )


def test_leap_year_has_8784_hourly_records():
    dataset = SyntheticLoadProvider().get_hourly_load(
        datetime(2024, 1, 1, tzinfo=timezone.utc),
        datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    assert len(dataset.timestamps) == 8784


def test_load_weather_timezone_representation_must_match(scenario_factory):
    inputs = scenario_factory(hours=1)
    different_offset = timezone(timedelta(hours=6))
    payload = inputs.model_dump()
    payload["load"] = LoadProfile(
        timestamps=[inputs.load.timestamps[0].astimezone(different_offset)],
        demand_kwh=[1],
    ).model_dump()
    with pytest.raises(ValidationError, match="timestamps must match exactly"):
        SimulationInput.model_validate(payload)
