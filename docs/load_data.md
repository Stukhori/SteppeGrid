# Electricity Load Data

## What SteppeGrid knows

SteppeGrid knows only the hourly electricity demand supplied to a scenario. A `LoadDataset` contains exact timestamps, total interval energy in kWh, optional critical interval energy in kWh, and load-specific provenance. It rejects negative values, gaps, duplicates, non-hourly intervals, and critical demand above total demand. Weather, load, and grid timestamps must match exactly, including their UTC-offset representation.

## What SteppeGrid does not know automatically

SteppeGrid does not know a village's true demand. No bundled profile is representative of Kazakhstan, a rural community, or a household. Defensible demand must come from measurement, utility records, bills, surveys, or an explicitly documented estimate. The deterministic `constant`, `residential_like`, and `community_facility_like` shapes are software fixtures only.

## Evidence hierarchy

From generally strongest to weakest for reconstructing hourly demand:

1. Calibrated hourly field-meter data with documented coverage and quality control.
2. Utility interval data with known meter scope and timestamp convention.
3. Monthly bills combined with a sourced and defensible intramonth profile.
4. Household or facility survey estimates with sampling and calculation methods.
5. Literature-derived assumptions with a relevant citation and transferability limits.
6. Synthetic profiles used for development and sensitivity tests.

These sources are not equivalent. Provenance uses `MEASURED`, `UTILITY_REPORTED`, `ESTIMATED_FROM_BILLS`, `LITERATURE_DERIVED`, `SYNTHETIC`, or `UNSPECIFIED`; choosing a label is a research assertion that must match the evidence.

## Preparing a CSV

Start from `examples/load/pilot_load_template.csv`. Replace all demonstration rows, cover the scenario's complete half-open interval `[start_time, end_time)`, and retain exactly one of these schemas:

```text
timestamp,total_load_kwh
timestamp,total_load_kwh,critical_load_kwh
```

Timestamps must be ISO 8601 with one consistent UTC offset, unique, chronological, and consecutive hourly. Values are interval energy in kWh, not instantaneous kW. Blank values are invalid. SteppeGrid performs no interpolation, resampling, or silent unit conversion.

Inspect before simulation:

```powershell
python -m steppegrid load inspect `
  --file examples/load/pilot_load_template.csv `
  --quality UNSPECIFIED
```

The template values are synthetic formatting examples and must not be used as pilot-site evidence.

## Literature-derived monthly constraints

A publication may provide monthly energy without releasing hourly values. SteppeGrid can reconstruct an existing `LoadDataset` by scaling a declared deterministic shape separately within each calendar month. The monthly source rows remain literature-derived; the hourly timing remains reconstructed and assumed.

The Rodina benchmark demonstrates two explicit source interpretations and three shapes. Its primary profile leaves critical load absent because the publication does not support a defensible critical-load series. See [Rodina benchmark](benchmarks/rodina.md).

## Scenario configuration

For a CSV relative to the scenario file:

```yaml
load:
  provider: csv
  path: ../load/pilot_load.csv
  source: Field meter export, instrument and dates recorded separately
  source_type: METER
  data_quality: MEASURED
```

For a deterministic demonstration:

```yaml
load:
  provider: synthetic
  profile: residential_like
  scale_factor: 0.75
  critical_fraction: 0.30
```

Synthetic values are assumptions, not observations. A complete calendar-year profile may use `target_annual_kwh`; other periods must use `scale_factor`. Total and critical series receive the same factor, which is retained in provenance. `target_annual_kwh` and `scale_factor` cannot both be active.

## Critical load

Critical demand is user-, facility-, and community-dependent. Lighting, communications, refrigeration, controls, medical equipment, and water systems may be critical in some contexts, but SteppeGrid does not hard-code any category as universally critical.

Supply explicit hourly `critical_load_kwh` when evidence exists. Otherwise `critical_fraction` applies one declared fraction to each total-load hour and provenance records that assumption. It must not be described as measured.

The default `proportional_or_existing` policy preserves total dispatch and allocates each hour's served energy to critical demand in the same proportion as total demand. `critical_first` changes only within-hour service accounting during outages: available served energy is allocated to critical demand first, then to non-critical demand. It does not forecast, reserve battery energy for future hours, optimize, or change total generation, battery use, grid import, curtailment, or total unserved energy.

Reported resilience quantities are primitive outage totals and the critical served fraction. A zero critical-demand denominator returns `0.0`; SteppeGrid does not create a composite resilience score.
