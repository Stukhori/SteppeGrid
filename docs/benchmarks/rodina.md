# Rodina Literature-Derived Village Benchmark

## Purpose

Rodina, Akmola Region, is useful as a Kazakhstan village-scale literature benchmark because the cited publication prints twelve monthly energy-balance rows and describes an annual simulation with a one-hour timestep. SteppeGrid uses those values to test source integrity and monthly-constrained load reconstruction. It does not treat the paper as a released smart-meter dataset or as independent validation of SteppeGrid.

Source: N. G. Dzhumamukhambetov, E. T. Yerbayev, D. A. Dzhaparova, Zh. G. Dzhumamukhambetov, and V. A. Yashkov, "Modeling of a Hybrid Energy System Based on Renewable Energy Sources and Storage Devices for the 'Rodina' Agricultural Settlement," *Herald of the National Engineering Academy of the Republic of Kazakhstan*, 2026, No. 1 (99), [DOI 10.47533/2026.1606-146X.1-03](https://doi.org/10.47533/2026.1606-146X.1-03).

## Published Evidence

`data/benchmarks/rodina/published_monthly_energy.csv` transcribes Table 1 without correction: monthly load, PV generation, wind generation, printed total generation, average storage SOC, and unserved load. `source_metadata.yaml` separately preserves printed annual totals, the approximate 7.8 GWh statement, one-hour/8,760-hour modelling statements, and contextual average-load ranges for the dairy plant, sports, social facilities, and household sector.

The category ranges are context only. SteppeGrid does not infer sector weights or automatically use their midpoints.

## Source Arithmetic

The publication's printed monthly rows and annual totals conflict:

| Quantity | Printed annual total (kWh) | Sum of monthly rows (kWh) | Calculated minus printed (kWh) |
|---|---:|---:|---:|
| Load | 7,720,000 | 8,020,000 | +300,000 |
| PV | 2,780,000 | 2,780,000 | 0 |
| Wind | 7,510,000 | 7,910,000 | +400,000 |
| Total generation | 10,290,000 | 10,690,000 | +400,000 |

These calculated values come from summing the transcribed rows in code. SteppeGrid preserves every printed value and reports the discrepancies rather than silently choosing or correcting one.

## Interpretations

`published_monthly_rows` is primary. Every monthly load value is used exactly as printed, so reconstructed annual energy is 8,020,000 kWh.

`annual_total_normalized` is an optional derived sensitivity case. One common factor, `7,720,000 / 8,020,000`, scales every printed monthly load while preserving relative seasonality. It is not a directly published series.

## Hourly Reconstruction

`flat_within_month` assigns one constant value to every hour in a month. It is the minimum-assumption baseline.

`residential_like` and `community_facility_like` independently scale SteppeGrid's deterministic synthetic hour-of-day templates within each month. These template names describe software fixtures, not observed Rodina behavior. Any final floating-point residual is assigned to the month's last hour and recorded in provenance so each target is conserved within `1e-6 kWh`.

The `reference_year` supplies calendar timestamps only. The publication does not establish that Table 1 represents 2025 or any other calendar year. For the paired benchmark, 2025 is a convenient non-leap carrier and UTC+05:00 is Rodina local civil time. This pairing convention does not turn the reconstructed values into measured 2025 demand or establish the timestamp convention of the paper's unpublished underlying model.

## Verified Site and Weather Pairing

`data/benchmarks/rodina/site.yaml` identifies Rodina, Tselinograd District, Akmola Region, Kazakhstan, at the requested ERA5 sampling anchor `51.302445, 70.541645`. Provenance classifies this as a verified point within or associated with Rodina; it is not asserted to be the exact village centroid, and the coordinate digits do not imply finer source precision.

The local 2025 half-open interval is `2025-01-01T00:00:00+05:00` to `2026-01-01T00:00:00+05:00`. Its matching UTC interval is `2024-12-31T19:00:00Z` to `2025-12-31T19:00:00Z`. Fetching a naive UTC January-to-January year would pair local evening behavior with the wrong weather hours and omit the required five-hour boundary segments.

SteppeGrid requests that exact shifted interval from the existing cached Open-Meteo ERA5 provider. Every local load timestamp is converted to the UTC instant used for matching; the load energy value is never shifted between local calendar months. Validation requires 8,760 consecutive rows, unique UTC and local timestamps, complete required values, exact one-to-one conversion, unchanged annual energy, and unchanged local monthly constraints.

For each primary shape, `aligned_hourly.csv` contains UTC and local timestamps, load, ERA5 2 m temperature, ERA5 10 m wind speed, and ERA5 shortwave radiation. Weather and load provenance remain separate. Load provenance retains `source_type=LITERATURE_DERIVED`, `reference_year=2025`, `reference_year_is_source_period=false`, `hourly_values_measured=false`, and `hourly_values_reconstructed=true`.

## Paired Diagnostics

Hourly Pearson correlations compare reconstructed load energy per hourly interval with coincident raw ERA5 shortwave radiation or 10 m wind speed. Monthly correlations compare local-calendar monthly load with monthly horizontal irradiation or monthly mean 10 m wind speed. Independently normalized plots show seasonality, representative winter and summer weeks, and typical local-day timing.

These statistics describe resource-demand temporal alignment only. Shortwave radiation is not PV generation, 10 m wind speed is not turbine generation, and correlation is not renewable coverage or system performance. No equipment, outage schedule, critical-load share, sizing, optimization, economics, or recommendation is introduced.

## Unknowns

The publication does not provide a machine-readable hourly load series, measurement method, meter coverage, timestamp timezone, or defensible village-wide critical-load series. Reconstructed profiles therefore have `critical_load_kwh=None` and `LITERATURE_DERIVED` provenance with `hourly_values_measured=false`.

Monthly energy is constrained by the publication, but intraday timing is not. Shape sensitivity is necessary because plausible deterministic templates produce different peak loads and timing while preserving identical monthly and annual energy. No shape is asserted to be true, and these peak differences do not support equipment sizing.

## Commands

```powershell
python -m steppegrid benchmark rodina validate

python -m steppegrid benchmark rodina build-load `
  --variant published_monthly_rows `
  --shape flat_within_month `
  --reference-year 2025 `
  --timezone-offset +05:00

python -m steppegrid benchmark rodina sensitivity `
  --variant published_monthly_rows `
  --reference-year 2025 `
  --timezone-offset +05:00

python -m steppegrid benchmark rodina pair-weather `
  --reference-year 2025 `
  --variant published_monthly_rows
```

Normal tests use deterministic weather fixtures and a fake Open-Meteo transport; they never require internet. The live paired command uses the weather cache, so an identical successful request becomes an offline-capable cache hit.
