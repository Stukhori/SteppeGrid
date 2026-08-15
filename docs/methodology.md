# Methodology

## System boundary and timestep

The simulation uses consecutive one-hour intervals. Input power is assumed constant within an interval, so an average output of `P kW` produces `P kWh` during that interval. Load is supplied as energy demand in kWh for each interval.

Every load, weather, and grid record must share the same timestamp. Missing intervals are rejected; the simulator never fills or interpolates missing time-series data.

## Quantities by provenance

### Measured inputs

None are bundled. Future measured inputs may include timestamped site demand, wind speed, irradiance, temperature, and empirical turbine power curves. Their sensor, height, calibration, sampling, aggregation, timezone, and quality-control metadata must accompany them outside the current domain model until a provenance schema is designed.

### External data

No data are fetched by the current code. Strict CSV providers can load user-supplied weather and turbine curves. Weather carries source, retrieval time, coordinates, coverage, units, and processing notes. Future emissions, tariff, equipment-cost, and conventional-turbine datasets must retain comparable source and license metadata.

### User-configurable assumptions

- Solar array DC capacity and aggregate performance ratio.
- Wind-turbine count and empirical wind-speed/output points.
- Battery capacity, initial and minimum state of charge, charge/discharge power limits, and one-way efficiencies.
- Hourly grid availability.
- Hourly electricity demand.

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

The current function provides one policy. A later policy interface should be introduced when a second real dispatch strategy is implemented.

## Metrics and conservation

`battery_charge_kwh` is renewable energy accepted at the battery input. `battery_discharge_kwh` is energy delivered from the battery to the load bus. For each charge, loss is `charge_input * (1 - charging_efficiency)`. For each discharge, loss is `energy_removed_from_SOC - energy_delivered_to_bus`. `battery_loss_kwh` is the sum of both losses.

`renewable_fraction = min(1, (renewable_direct_to_load + battery_discharge_to_load) / total_demand)`. This preserves the original definition. It assumes initial battery energy is renewable because the model does not yet track energy provenance. The ambiguity is material: a scenario initialized from grid-charged storage would overstate renewable contribution. Provenance-aware storage must replace this assumption before external reporting.

For hours with `grid_available = false`, `outage_unserved_energy_kwh` is the sum of unserved load, `outage_demand_kwh` is the sum of demand, and `outage_served_energy_kwh = outage_demand_kwh - outage_unserved_energy_kwh`. Grid imports are necessarily zero in these hours.

For each hour, tests verify:

```text
renewable generation + grid import + starting battery SOC
= served demand + curtailment + ending battery SOC + battery loss
```

where served demand is total demand minus unserved energy.

Outages may be supplied as an hourly boolean series or constructed from timestamp intervals. Interval starts are inclusive and ends are exclusive. Outage metrics are primitive totals over intervals where `grid.available` is false: outage demand, served energy, and unserved energy. No composite resilience score is asserted.

## Weather normalization

`WeatherProvider` returns a `WeatherDataset` containing normalized `WeatherSeries` plus `DataProvenance`. The simulator sees only `WeatherSeries`, so adding a historical provider does not alter dispatch code. The CSV provider selects `[start, end)`, requires every requested hour, and performs no unit conversion or interpolation. Its configurable default irradiance validation ceiling is 2000 W/m2; this is a corruption-screening assumption, not a physical maximum.
