import csv
import io
import math
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from steppegrid.planning.demand import (
    PlanningDemandError,
    estimated_annual_demand,
    estimated_monthly_demand,
    parse_hourly_demand_csv,
)
from steppegrid.planning.models import (
    DemandConfidence,
    DemandMode,
    DemandSourceType,
    DemandSpecification,
    PlanningScenario,
    PlanningSite,
    SitePreset,
    TechnologySelection,
)


def _annual(value=500_000, year=2025):
    return estimated_annual_demand(
        value, reference_year=year, timezone_offset="+00:00",
        shape="community_facility_like", shape_timezone_offset="+05:00",
        source_type=DemandSourceType.SYNTHETIC_ESTIMATE,
        confidence=DemandConfidence.SYNTHETIC_PLANNING_ESTIMATE,
        method="Explicit user planning estimate",
    )


def test_annual_and_monthly_estimates_conserve_inputs_exactly():
    annual = _annual(500_000)
    assert len(annual.timestamps) == 8760
    assert annual.annual_kwh == pytest.approx(500_000, abs=1e-8)
    monthly_targets = tuple(10_000.0 * month for month in range(1, 13))
    monthly = estimated_monthly_demand(
        monthly_targets, reference_year=2024, timezone_offset="+00:00",
        shape="residential_like", shape_timezone_offset="+05:00",
        source_type=DemandSourceType.PROXY_DERIVED,
        confidence=DemandConfidence.PROXY_ESTIMATE,
        method="Explicit monthly proxy", source_name="User-declared source",
    )
    assert len(monthly.timestamps) == 8784
    for month, target in enumerate(monthly_targets, start=1):
        actual = math.fsum(value for timestamp, value in zip(monthly.timestamps, monthly.demand_kwh, strict=True) if timestamp.month == month)
        assert actual == pytest.approx(target, abs=1e-8)


@pytest.mark.parametrize("shape", ["flat_within_month", "residential_like", "community_facility_like"])
def test_every_supported_synthetic_shape_is_deterministic(shape):
    kwargs = dict(
        reference_year=2025, timezone_offset="+00:00", shape=shape,
        source_type=DemandSourceType.SYNTHETIC_ESTIMATE,
        confidence=DemandConfidence.SYNTHETIC_PLANNING_ESTIMATE,
        method="Determinism test",
    )
    first = estimated_annual_demand(500_000, **kwargs)
    second = estimated_annual_demand(500_000, **kwargs)
    assert first.demand_kwh == second.demand_kwh
    assert first.sha256 == second.sha256
    assert first.annual_kwh == pytest.approx(500_000, abs=1e-8)
    assert min(first.demand_kwh) >= 0


def _csv_payload(*, hours=8760, duplicate=False, missing=False, bad_value=None):
    output = io.StringIO(); writer = csv.writer(output)
    writer.writerow(["timestamp", "demand_kwh"])
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    for index in range(hours):
        timestamp = start + timedelta(hours=index + (1 if missing and index >= 10 else 0))
        if duplicate and index == 10:
            timestamp = start + timedelta(hours=9)
        value = bad_value if bad_value is not None and index == 10 else 1.0
        writer.writerow([timestamp.isoformat(), value])
    return output.getvalue()


def test_hourly_upload_accepts_strict_valid_schema():
    demand = parse_hourly_demand_csv(_csv_payload())
    assert len(demand.timestamps) == 8760
    assert demand.annual_kwh == 8760
    assert demand.source_type is DemandSourceType.USER_PROVIDED
    assert len(demand.sha256) == 64


@pytest.mark.parametrize(
    "case, message",
    [
        ("schema", "exactly"),
        ("short", "8,760 or 8,784"),
        ("duplicate", "duplicate"),
        ("missing", "consecutive"),
        ("nan", "finite"),
        ("negative", "non-negative"),
    ],
)
def test_hourly_upload_rejects_invalid_data(case, message):
    payload = {
        "schema": lambda: "time,demand_kwh\n",
        "short": lambda: _csv_payload(hours=8759),
        "duplicate": lambda: _csv_payload(duplicate=True),
        "missing": lambda: _csv_payload(missing=True),
        "nan": lambda: _csv_payload(bad_value="NaN"),
        "negative": lambda: _csv_payload(bad_value=-1),
    }[case]()
    with pytest.raises(PlanningDemandError, match=message):
        parse_hourly_demand_csv(payload)


def test_shamshi_requires_explicit_demand_and_proxy_source():
    site = PlanningSite(
        preset=SitePreset.SHAMSHI, name="Shamshi Kaldayakova",
        latitude=50.578333, longitude=57.544722, timezone_offset="+05:00",
    )
    technologies = TechnologySelection(wind_keys=("sd6",), pv_keys=(), battery_keys=())
    with pytest.raises(ValidationError, match="annual_kwh"):
        DemandSpecification(
            mode=DemandMode.ESTIMATED_ANNUAL,
            source_type=DemandSourceType.SYNTHETIC_ESTIMATE,
            confidence=DemandConfidence.SYNTHETIC_PLANNING_ESTIMATE,
            method_notes="No value supplied",
        )
    with pytest.raises(ValidationError, match="visible source name"):
        DemandSpecification(
            mode=DemandMode.ESTIMATED_ANNUAL,
            source_type=DemandSourceType.PROXY_DERIVED,
            confidence=DemandConfidence.PROXY_ESTIMATE,
            annual_kwh=500_000,
            method_notes="Proxy method",
        )
    with pytest.raises(ValidationError, match="Rodina benchmark"):
        PlanningScenario(
            name="Invalid hidden substitution", site=site,
            demand=DemandSpecification(
                mode=DemandMode.RODINA_BENCHMARK,
                source_type=DemandSourceType.SOURCE_RECONSTRUCTED,
                confidence=DemandConfidence.STRONG_SOURCE_RECONSTRUCTION,
                method_notes="Rodina demand",
            ),
            reliability_target=0.95, technologies=technologies,
        )


def test_scenario_hash_is_deterministic_and_input_sensitive():
    site = PlanningSite(preset=SitePreset.CUSTOM, name="Test", latitude=50, longitude=60)
    demand = DemandSpecification(
        mode=DemandMode.ESTIMATED_ANNUAL,
        source_type=DemandSourceType.SYNTHETIC_ESTIMATE,
        confidence=DemandConfidence.SYNTHETIC_PLANNING_ESTIMATE,
        annual_kwh=500_000, method_notes="Explicit test",
    )
    base = dict(name="Test", site=site, demand=demand, technologies=TechnologySelection(wind_keys=("sd6",)))
    lower = PlanningScenario(**base, reliability_target=0.95)
    repeated = PlanningScenario(**base, reliability_target=0.95)
    higher = PlanningScenario(**base, reliability_target=0.99)
    assert lower.input_hash == repeated.input_hash
    assert lower.scenario_id == repeated.scenario_id
    assert lower.input_hash != higher.input_hash
