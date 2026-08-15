from __future__ import annotations

import csv
import math

import pytest

from steppegrid.benchmarks.outputs import write_reconstruction, write_source_integrity
from steppegrid.benchmarks.reconstruction import monthly_targets, reconstruct_hourly_load
from steppegrid.benchmarks.sensitivity import build_shape_sensitivity
from steppegrid.benchmarks.source import (
    load_monthly_benchmark,
    validate_source_integrity,
)
from steppegrid.simulation.models import LoadDataQuality, LoadSourceType


PUBLISHED_LOAD = [
    680000,
    610000,
    640000,
    590000,
    650000,
    710000,
    720000,
    700000,
    650000,
    690000,
    670000,
    710000,
]
PUBLISHED_PV = [
    110000,
    140000,
    190000,
    250000,
    310000,
    340000,
    350000,
    330000,
    270000,
    210000,
    160000,
    120000,
]
PUBLISHED_WIND = [
    720000,
    680000,
    710000,
    650000,
    610000,
    590000,
    600000,
    610000,
    650000,
    680000,
    690000,
    720000,
]


def _source():
    return load_monthly_benchmark()


def test_source_transcription_preserves_all_twelve_printed_rows():
    source = _source()
    assert [row.load_kwh for row in source.rows] == PUBLISHED_LOAD
    assert [row.pv_generation_kwh for row in source.rows] == PUBLISHED_PV
    assert [row.wind_generation_kwh for row in source.rows] == PUBLISHED_WIND
    assert [row.published_total_generation_kwh for row in source.rows] == [
        pv + wind for pv, wind in zip(PUBLISHED_PV, PUBLISHED_WIND, strict=True)
    ]
    assert all(row.published_unserved_kwh == 0 for row in source.rows)


def test_integrity_report_uses_row_arithmetic_and_exposes_source_mismatches():
    source = _source()
    report = validate_source_integrity(source)
    comparisons = (
        (report.load, [row.load_kwh for row in source.rows]),
        (report.pv, [row.pv_generation_kwh for row in source.rows]),
        (report.wind, [row.wind_generation_kwh for row in source.rows]),
        (
            report.generation,
            [row.published_total_generation_kwh for row in source.rows],
        ),
    )
    for comparison, values in comparisons:
        assert comparison.calculated_monthly_sum_kwh == sum(values)
        assert comparison.difference_kwh == (
            sum(values) - comparison.published_annual_kwh
        )
    assert not report.load.matches
    assert report.pv.matches
    assert not report.wind.matches
    assert not report.generation.matches
    assert report.known_source_inconsistency


@pytest.mark.parametrize(
    "shape", ["flat_within_month", "residential_like", "community_facility_like"]
)
def test_every_shape_conserves_each_published_month(shape):
    result = reconstruct_hourly_load(
        _source(),
        variant="published_monthly_rows",
        shape=shape,
        reference_year=2025,
    )
    assert [row.source_target_kwh for row in result.validation] == PUBLISHED_LOAD
    assert all(row.absolute_error_kwh <= 1e-6 for row in result.validation)
    for month, target in enumerate(PUBLISHED_LOAD, start=1):
        reconstructed = math.fsum(
            value
            for timestamp, value in zip(
                result.dataset.timestamps, result.dataset.total_load_kwh, strict=True
            )
            if timestamp.month == month
        )
        assert reconstructed == pytest.approx(target, abs=1e-6)


def test_annual_total_normalized_variant_matches_printed_total_and_preserves_proportions():
    source = _source()
    targets, factor = monthly_targets(source, "annual_total_normalized")
    result = reconstruct_hourly_load(
        source,
        variant="annual_total_normalized",
        shape="flat_within_month",
        reference_year=2025,
    )
    assert math.fsum(result.dataset.total_load_kwh) == pytest.approx(
        source.provenance.published_annual_load_kwh, abs=1e-6
    )
    assert all(
        target / published == pytest.approx(factor)
        for target, published in zip(targets, PUBLISHED_LOAD, strict=True)
    )
    assert result.dataset.provenance.scaling_factor == pytest.approx(factor)


@pytest.mark.parametrize(("year", "records"), [(2025, 8760), (2024, 8784)])
def test_reference_year_supports_normal_and_leap_calendar_carriers(year, records):
    result = reconstruct_hourly_load(
        _source(),
        variant="published_monthly_rows",
        shape="flat_within_month",
        reference_year=year,
        timezone_offset="+06:00",
    )
    assert len(result.dataset.timestamps) == records
    assert result.dataset.timestamps[0].isoformat().endswith("+06:00")
    assert all(row.absolute_error_kwh <= 1e-6 for row in result.validation)


def test_provenance_is_literature_derived_reconstructed_and_serializable():
    result = reconstruct_hourly_load(
        _source(),
        variant="published_monthly_rows",
        shape="residential_like",
        reference_year=2025,
    )
    provenance = result.dataset.provenance
    assert provenance.source_type is LoadSourceType.LITERATURE_DERIVED
    assert provenance.data_quality is LoadDataQuality.LITERATURE_DERIVED
    assert provenance.published_values_transcribed is True
    assert provenance.hourly_values_measured is False
    assert provenance.hourly_values_reconstructed is True
    assert provenance.reference_year_is_source_period is False
    assert provenance.known_source_inconsistency is True
    assert provenance.model_validate_json(provenance.model_dump_json()) == provenance
    assert result.dataset.critical_load_kwh is None


def test_reconstruction_and_shape_sensitivity_are_reproducible():
    source = _source()
    first = build_shape_sensitivity(
        source,
        variant="published_monthly_rows",
        reference_year=2025,
        timezone_offset="+00:00",
    )
    second = build_shape_sensitivity(
        source,
        variant="published_monthly_rows",
        reference_year=2025,
        timezone_offset="+00:00",
    )
    assert first == second
    assert len({result.summary.peak_hourly_load_kwh for result in first}) == 3


def test_benchmark_outputs_include_integrity_and_monthly_validation(tmp_path):
    source = _source()
    integrity = validate_source_integrity(source)
    write_source_integrity(integrity, tmp_path)
    result = reconstruct_hourly_load(
        source,
        variant="published_monthly_rows",
        shape="flat_within_month",
        reference_year=2025,
    )
    reconstruction = write_reconstruction(result, tmp_path / "load")
    assert (tmp_path / "source_integrity.json").is_file()
    assert "Known source inconsistency detected: yes" in (
        tmp_path / "source_integrity.md"
    ).read_text(encoding="utf-8")
    with (reconstruction / "monthly_validation.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 12
    assert max(float(row["absolute_error_kwh"]) for row in rows) <= 1e-6
    with (reconstruction / "hourly_load.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        hourly_rows = list(csv.DictReader(handle))
    assert "T" in hourly_rows[0]["timestamp"]
