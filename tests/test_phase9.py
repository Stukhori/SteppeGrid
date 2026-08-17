from datetime import datetime, timedelta, timezone
import math

import pytest

from steppegrid.benchmarks.phase9 import (
    HYBRID_PV_SHARE, HYBRID_WIND_SHARE, REFERENCE_AZIMUTH_DEG,
    REFERENCE_TILT_DEG, normalize_to_annual_energy, run_phase9,
)
from steppegrid.simulation.models import DataProvenance, WeatherDataset, WeatherSeries
from steppegrid.weather.open_meteo import REQUESTED_VARIABLES


@pytest.fixture(scope="module")
def phase9_run():
    start=datetime(2024,12,31,19,tzinfo=timezone.utc)
    timestamps=[start+timedelta(hours=i) for i in range(8760)]
    local=[t.astimezone(timezone(timedelta(hours=5))) for t in timestamps]
    daylight=[max(0,math.sin(math.pi*(t.hour-6)/12)) for t in local]
    seasonal=[.65+.35*math.sin(2*math.pi*(t.timetuple().tm_yday-80)/365) for t in local]
    ghi=[800*d*s for d,s in zip(daylight,seasonal,strict=True)]
    dhi=[.2*v for v in ghi]
    dni=[max(0,(g-d)/max(.2,day)) for g,d,day in zip(ghi,dhi,daylight,strict=True)]
    wind100=[6+1.5*math.cos(2*math.pi*t.timetuple().tm_yday/365)+.4*math.cos(2*math.pi*t.hour/24) for t in local]
    weather=WeatherDataset(series=WeatherSeries(timestamps=timestamps,wind_speed_m_s=[v*.8 for v in wind100],
        wind_speed_100m_m_s=wind100,solar_irradiance_w_m2=ghi,direct_normal_irradiance_w_m2=dni,
        diffuse_radiation_w_m2=dhi,temperature_c=[5+20*math.sin(2*math.pi*(t.timetuple().tm_yday-105)/365) for t in local]),
        provenance=DataProvenance(source="deterministic Phase 9 test weather",provider="test",underlying_model="ERA5",
            start_time=timestamps[0],end_time=timestamps[-1]+timedelta(hours=1),original_units={v:"test SI" for v in REQUESTED_VARIABLES},
            normalized_units={},variables_requested=list(REQUESTED_VARIABLES)))
    return run_phase9(weather=weather,write_outputs=False)


def test_phase9_dataset_integrity_and_load_alignment(phase9_run):
    assert phase9_run.weather_integrity["records"]==8760
    assert phase9_run.load_integrity["records_per_shape"]==8760
    assert phase9_run.load_integrity["timezone"]=="+05:00"
    assert phase9_run.load_integrity["annual_kwh"]==pytest.approx(8_020_000)
    assert phase9_run.load_integrity["hourly_values_measured"] is False


def test_wind_annual_sums_and_capacity_factor(phase9_run):
    for key,row in phase9_run.wind.items():
        if key=="resource": continue
        assert row["annual_generation_kwh"]==pytest.approx(math.fsum(phase9_run.wind_profiles_kwh[key]))
        assert row["capacity_factor"]==pytest.approx(row["annual_generation_kwh"]/(row["rated_power_kw"]*8760))
        assert math.isfinite(row["capacity_factor"]) and row["capacity_factor"]>=0


def test_all_turbines_use_one_derived_alpha_and_fixed_hubs(phase9_run):
    alpha=phase9_run.wind_shear["exponent"]
    assert alpha!=pytest.approx(1/7)
    expected_hubs={"skystream_3_7":10.7,"sd6":9,"bergey_excel_15":30}
    for key,hub in expected_hubs.items():
        assert phase9_run.wind[key]["shear_exponent"]==pytest.approx(alpha)
        assert phase9_run.wind[key]["hub_height_m"]==hub
        assert phase9_run.wind_generic_reference[key]["shear_exponent"]==pytest.approx(1/7)


def test_derived_shear_reconstructs_two_height_fixture_better_than_generic(phase9_run):
    derived=phase9_run.wind_shear["derived_reconstruction"]
    generic=phase9_run.wind_shear["generic_one_seventh_reconstruction"]
    assert derived["mae_m_s"]<generic["mae_m_s"]
    assert derived["rmse_m_s"]<generic["rmse_m_s"]


def test_pv_sums_fixed_orientation_and_no_tilt_search(phase9_run):
    for key,row in phase9_run.pv.items():
        assert row["annual_ac_kwh"]==pytest.approx(math.fsum(phase9_run.pv_profiles_kwh[key]))
        assert row["annual_dc_kwh"]>=row["annual_ac_kwh"]
        assert row["clipping_kwh"]>=0 and row["inverter_conversion_loss_kwh"]>=0
        assert row["tilt_deg"]==REFERENCE_TILT_DEG
        assert row["azimuth_deg"]==REFERENCE_AZIMUTH_DEG


def test_analytical_normalization_and_coincidence_conservation(phase9_run):
    target=phase9_run.load_integrity["annual_kwh"]
    normalized=normalize_to_annual_energy(next(iter(phase9_run.wind_profiles_kwh.values())),target)
    assert math.fsum(normalized)==pytest.approx(target)
    for row in phase9_run.coincidence:
        assert row["annual_generation_kwh"]==pytest.approx(row["direct_kwh"]+row["surplus_kwh"])
        assert row["annual_load_kwh"]==pytest.approx(row["direct_kwh"]+row["unmet_kwh"])
        assert min(row["direct_kwh"],row["surplus_kwh"],row["unmet_kwh"])>=0
        assert row["analytical_normalization_only"] is True


def test_fixed_hybrid_is_exactly_50_50_without_search(phase9_run):
    assert HYBRID_WIND_SHARE==HYBRID_PV_SHARE==.5
    hybrids=[r for r in phase9_run.coincidence if r["category"]=="hybrid_50_50"]
    assert len(hybrids)==3*3*6
    assert all(r["annual_generation_kwh"]==pytest.approx(r["annual_load_kwh"]) for r in hybrids)


def test_complementarity_metrics_are_bounded(phase9_run):
    assert len(phase9_run.complementarity)==3*6
    for row in phase9_run.complementarity:
        assert row["pearson_correlation"] is None or -1<=row["pearson_correlation"]<=1
        assert 0<=row["both_low_hours"]<=8760
        assert 0<=row["at_least_one_producing_hours"]<=8760


def test_one_unit_storage_has_no_gifted_inventory_and_conserves_energy(phase9_run):
    assert len(phase9_run.storage)==3*2
    for row in phase9_run.storage:
        assert row["battery_count"]==1
        assert row["discharge_from_initial_inventory_kwh"]==pytest.approx(0,abs=1e-9)
        assert abs(row["energy_balance_generation_error_kwh"])<1e-6
        assert abs(row["energy_balance_load_error_kwh"])<1e-6
        assert abs(row["energy_balance_storage_error_kwh"])<1e-6
        assert row["ending_soc_kwh"]>=row["starting_soc_kwh"]-1e-9
        assert row["unmet_improvement_kwh"]>=0


def test_phase9_exposes_no_optimizer_or_ranking(phase9_run):
    assert not hasattr(phase9_run,"optimizer")
    assert not hasattr(phase9_run,"ranking")
