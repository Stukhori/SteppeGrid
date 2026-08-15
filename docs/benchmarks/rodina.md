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

The `reference_year` supplies calendar timestamps only. The publication does not establish that Table 1 represents 2025 or any other calendar year. A configurable fixed UTC offset is likewise a simulation carrier, not an inferred Rodina measurement timezone.

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
  --timezone-offset +00:00

python -m steppegrid benchmark rodina sensitivity `
  --variant published_monthly_rows `
  --reference-year 2025 `
  --timezone-offset +00:00
```

Normal tests read only the checked-in CSV/YAML transcription and never contact the publication website.
