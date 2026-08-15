# Methodology

## System boundary and timestep

The simulation uses consecutive one-hour intervals. Input power is assumed constant within an interval, so an average output of `P kW` produces `P kWh` during that interval. Load is supplied as energy demand in kWh for each interval.

Every load, weather, and grid record must share the same timestamp. Missing intervals are rejected; the simulator never fills or interpolates missing time-series data.

## Quantities by provenance

### Measured inputs

None are bundled. User-supplied hourly load may be classified as measured only when its source supports that claim. Load provenance records source type, evidence quality, location, coverage, units, processing, scaling, and the method used to define critical demand. Weather and turbine evidence retain their existing provenance boundaries.

### External data

Open-Meteo ERA5 reanalysis can be fetched and cached; strict CSV providers can also load user-supplied weather and turbine curves. Weather carries source, retrieval time, requested and returned coordinates, coverage, units, and processing notes. Future emissions, tariff, equipment-cost, and conventional-turbine datasets must retain comparable source and license metadata.

### User-configurable assumptions

- Solar array DC capacity and aggregate performance ratio.
- Wind-turbine count and empirical wind-speed/output points.
- Battery capacity, initial and minimum state of charge, charge/discharge power limits, and one-way efficiencies.
- Hourly grid availability.
- Hourly electricity demand.
- Optional hourly critical demand or an explicitly assumed critical fraction.
- Outage load-service allocation policy.

### Calculated quantities

Solar output, interpolated wind output, renewable energy sent directly to load, battery flows and state of charge, grid imports, curtailment, unserved energy, battery losses, and aggregate totals are calculated by the engine.

## Component calculations

Solar output uses a deliberately simple relationship:

```text
solar_output_kw = min(
    dc_capacity_kw,
    dc_capacity_kw * irradiance_w_m2 / 1000 * performance_ratio,
)
```

The reference irradiance of 1000 W/m2 is part of the PV rating convention, not a local resource claim. Temperature, incidence angle, shading, snow, inverter clipping details, degradation, and spectral effects are not separately modelled.

Wind output is linear interpolation between user-supplied empirical power-curve points. At an exact point, its supplied power is returned. Below the minimum or above the maximum wind speed, the respective endpoint output is returned. A valid curve must therefore explicitly encode the intended zero-output cut-in and cut-out behavior. The engine does not infer turbine aerodynamics or HelixGen performance.

Battery charging converts bus energy to stored energy using charging efficiency. Discharging removes more stored energy than it delivers to the bus according to discharging efficiency. Minimum SOC and hourly power limits are enforced.

## Dispatch policy

For every hour, the fixed policy is:

1. Solar and wind serve load directly.
2. Renewable surplus charges the battery.
3. The battery serves the remaining deficit.
4. An available grid serves the residual deficit.
5. Any residual becomes unserved energy.
6. Renewable surplus that cannot be stored is curtailed.

Total-energy dispatch remains this single policy. Critical service is then attributed without changing total flows. `proportional_or_existing` multiplies critical demand by the hour's total served fraction. During grid outages, `critical_first` instead assigns available served energy to critical demand before non-critical demand. It does not reserve energy across hours or automatically shed load in the physical dispatch calculation.

## Metrics and conservation

`battery_charge_kwh` is renewable energy accepted at the battery input. `battery_discharge_kwh` is energy delivered from the battery to the load bus. For each charge, loss is `charge_input * (1 - charging_efficiency)`. For each discharge, loss is `energy_removed_from_SOC - energy_delivered_to_bus`. `battery_loss_kwh` is the sum of both losses.

`renewable_fraction = min(1, (renewable_direct_to_load + battery_discharge_to_load) / total_demand)`. This preserves the original definition. It assumes initial battery energy is renewable because the model does not yet track energy provenance. The ambiguity is material: a scenario initialized from grid-charged storage would overstate renewable contribution. Provenance-aware storage must replace this assumption before external reporting.

For hours with `grid_available = false`, `outage_unserved_energy_kwh` is the sum of unserved load, `outage_demand_kwh` is the sum of demand, and `outage_served_energy_kwh = outage_demand_kwh - outage_unserved_energy_kwh`. Grid imports are necessarily zero in these hours.

The explicit total aliases are `outage_total_demand_kwh`, `outage_total_served_kwh`, and `outage_total_unserved_kwh`. Critical counterparts sum the hourly critical accounting fields. `critical_load_served_fraction` divides outage critical served energy by outage critical demand; a zero denominator returns `0.0`. No composite score is calculated.

For each hour, tests verify:

```text
renewable generation + grid import + starting battery SOC
= served demand + curtailment + ending battery SOC + battery loss
```

where served demand is total demand minus unserved energy.

Outages may be supplied as an hourly boolean series or constructed from timestamp intervals. Interval starts are inclusive and ends are exclusive. Outage metrics are primitive totals over intervals where `grid.available` is false: outage demand, served energy, and unserved energy. No composite resilience score is asserted.

## Load normalization

`LoadProvider` returns a `LoadDataset` with total load, optional critical load, and `LoadProvenance`. CSV timestamps require a consistent explicit UTC offset and consecutive hourly coverage. Scenario resolution requires ISO-formatted timestamp equality across load, weather, and grid, so a different start, end, offset representation, missing hour, or leap-year length fails rather than truncating data.

Reference profiles can use one positive `scale_factor`. A complete January-to-January calendar year can instead use `target_annual_kwh`; the factor is the target divided by the original sum. Both total and critical energy are multiplied consistently and the factor is recorded. No interpolation or shape modification occurs.

## Weather normalization

`WeatherProvider` returns a `WeatherDataset` containing normalized `WeatherSeries` plus `DataProvenance`. The simulator sees only `WeatherSeries`, so adding a historical provider does not alter dispatch code. The CSV provider selects `[start, end)`, requires every requested hour, and performs no unit conversion or interpolation. Its configurable default irradiance validation ceiling is 2000 W/m2; this is a corruption-screening assumption, not a physical maximum.

### Open-Meteo ERA5 provider

`OpenMeteoHistoricalWeatherProvider` calls the official [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api) archive endpoint and explicitly selects `models=era5`. It requests hourly 2 m temperature, 10 m wind speed, and shortwave radiation in UTC, celsius, m/s, and W/m2. Open-Meteo defines shortwave radiation as the mean over the preceding hour. SteppeGrid renames fields but performs no numeric unit conversion.

Open-Meteo accepts inclusive calendar dates, while SteppeGrid uses half-open datetime intervals `[start, end)`. The provider requests the inclusive API dates needed to cover the interval, then validates and selects every expected UTC hour. This handles leap years without assuming 8,760 hours.

Provenance `requested_start_date` and `requested_end_date` preserve the SteppeGrid request, with the end date exclusive. `metadata.json` separately retains the inclusive `end_date` parameter actually sent to Open-Meteo.

ERA5 is historical reanalysis: a numerical reconstruction informed by observations, not an exact measurement at the requested house or village. ERA5 has a dataset-level grid resolution of 0.25 degrees (approximately 25 km). Open-Meteo may return a grid-cell coordinate different from the request; both coordinates and their approximate great-circle separation are recorded.

The 10 m wind series is passed to the current wind power curve without hub-height adjustment. This is a known physical mismatch for turbines whose curve applies at another height. No unvalidated wind-shear or terrain correction is applied.

### Cache and audit trail

The cache key hashes provider, model, requested coordinates, exact start/end datetimes, variables, units, and timezone. A complete entry contains `raw.json`, deterministic normalized `weather.csv`, and `metadata.json`. Normal cache use never refreshes automatically. `--refresh` is explicit. Cache hits normalize from retained raw JSON again, so the source/transformation boundary remains auditable and cached data remain usable offline.

## Pilot-site resource analysis

Pilot analysis requires one complete UTC calendar year: 8,760 hours normally or 8,784 hours in a leap year. Expected timestamps are generated from the configured half-open interval; no fixed annual count is assumed without checking the calendar.

Wind summaries use ERA5 10 m wind speed. Percentiles use linear interpolation between ordered observations, and standard deviation is the population standard deviation for the analyzed year. Speed bands are descriptive only and have no turbine-operating interpretation.

Open-Meteo shortwave radiation is a preceding-hour mean in W/m2. Each record represents one hour, so monthly and annual horizontal irradiation use `sum(irradiance_w_m2 * 1 hour) / 1000`, producing kWh/m2. No panel-plane transformation is implied.

The seasonal plot independently min-max normalizes the 12 monthly mean wind values and 12 monthly irradiation totals. The reported Pearson correlation is between those same 12 unnormalized series. It describes monthly association only and does not demonstrate energy-system complementarity or resilience.
