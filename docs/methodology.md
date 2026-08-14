# Methodology

## System boundary and timestep

The simulation uses consecutive one-hour intervals. Input power is assumed constant within an interval, so an average output of `P kW` produces `P kWh` during that interval. Load is supplied as energy demand in kWh for each interval.

Every load, weather, and grid record must share the same timestamp. Missing intervals are rejected; the simulator never fills or interpolates missing time-series data.

## Quantities by provenance

### Measured inputs

None are bundled. Future measured inputs may include timestamped site demand, wind speed, irradiance, temperature, and empirical turbine power curves. Their sensor, height, calibration, sampling, aggregation, timezone, and quality-control metadata must accompany them outside the current domain model until a provenance schema is designed.

### External data

None are fetched by the current code. Future external weather, emissions, tariff, equipment-cost, and conventional-turbine curve datasets must retain source and license metadata. Import and cleaning belong in a separate ingestion layer.

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

Wind output is linear interpolation between user-supplied empirical power-curve points. Outside the supplied wind-speed range, the nearest endpoint output is used. A valid curve should therefore explicitly include the intended zero-output cut-in and cut-out behavior. The engine does not infer turbine aerodynamics or HelixGen performance.

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

`battery_charge_kwh` is renewable energy accepted at the battery input. `battery_discharge_kwh` is energy delivered from the battery to the load bus. Battery loss includes both charging and discharging conversion loss.

The renewable fraction is defined as renewable energy delivered directly to load plus battery discharge delivered to load, divided by total demand, capped at one. This assumes initial battery energy is renewable because the model does not yet track energy provenance. That assumption is explicit and must be replaced with provenance-aware state before renewable reporting is used externally.

For each hour, tests verify:

```text
renewable generation + grid import + starting battery SOC
= served demand + curtailment + ending battery SOC + battery loss
```

where served demand is total demand minus unserved energy.

Outages may be supplied as an hourly boolean series or constructed from timestamp intervals. Interval starts are inclusive and ends are exclusive. Outage metrics are primitive totals over intervals where `grid.available` is false: outage demand, served energy, and unserved energy. No composite resilience score is asserted.
