# SteppeGrid

## Executive Summary

SteppeGrid v1.0 is a reproducible renewable microgrid planning platform for seven rural Kazakhstan settlements. It joins repository-registered electricity demand with cached hourly ERA5 weather, equipment models, battery dispatch, discrete sizing, reliability analysis, and lifecycle planning economics. The public interface emphasizes decisions and results while the technical data lineage remains in the repository.

## Problem

Remote communities need a transparent way to explore how local demand and renewable resources affect system scale, reliability, and cost. SteppeGrid answers that planning question with hourly—not annual-average—energy balancing.

## Platform Architecture

Typed site and demand records feed weather and generation services. Wind and PV traces enter hourly load-first dispatch with constrained battery state of charge. A discrete optimizer evaluates supported equipment combinations. Read-only application services load frozen benchmark and saved scenario artifacts without recomputation.

## Kazakhstan Sites

The production registry contains exactly Rodina, Shamshi Kaldayakova, Katon-Karagay, Kegen, Shayan, Sai-Otes, and Togyzkuduk. Their current registered annual demands are 8.02, 0.50, 2.96, 8.00, 8.17, 1.51, and 0.89 GWh/year respectively.

## Electricity Demand

Each planning run uses an 8,760-hour trace. Registered datasets provide current application values; planner users may instead enter annual totals, twelve monthly totals, or an hourly CSV. Hashes, source records, and scenario snapshots remain available for reproduction.

## Weather

Each site has repository-relative cached 2025 ERA5 data. Application startup does not download weather. ERA5 is gridded reanalysis and is described as modeled weather rather than an on-site measurement.

## Wind Modeling

Hourly wind is adjusted to equipment hub height and passed through discrete turbine power curves. Equipment identity and rating remain explicit.

## PV Modeling

Irradiance and temperature drive tilted-array PV output, which is constrained by the selected inverter. Results distinguish DC and AC capacity.

## Storage and Dispatch

Renewables serve load first. Surplus charges storage within energy, power, and efficiency constraints. Storage then serves deficits; remaining surplus is curtailment and remaining deficit is unmet electricity.

## Reliability

The primary metric is annual energy served. SteppeGrid separately reports unmet electricity, loss-of-load hours, longest deficit duration, and maximum hourly deficit. Energy served is not uptime.

## Optimization

The established Planner V2 discrete search selects supported wind, solar, and battery equipment for 95% or 99% annual energy served. This release changes no optimizer or physical methodology.

## Economics

Planning outputs include CAPEX, net present cost (NPC), equivalent annual cost (EAC), and cost per served kWh using the established reference assumptions.

## Rodina Benchmark

The unchanged benchmark selects 2.04 MW wind, 8.30 MWac PV, and 15.42 MWh usable storage for 95.04% annual energy served, with $36.52M CAPEX, $49.38M NPC, and $2.84M/year EAC. The 99% design selects 4.98 MW wind, 20.20 MWac PV, and 23.12 MWh storage for 99.00% served energy, with $81.96M CAPEX, $105.79M NPC, and $6.08M/year EAC.

## Cross-Village Analysis

The interface compares only saved compatible results and normalizes capacity or cost by registered annual demand where appropriate. Because a complete saved paired result set is absent, v1.0 does not publish unsupported seven-site winner rankings.

## My Village — Shamshi Kaldayakova

Shamshi Kaldayakova (Aktobe Region) is the featured blue `MY VILLAGE` case. Its current registered demand is 0.50 GWh/year. Cached weather contains 8,760 modeled hours. The latest saved 95% system uses 348.4 kW wind, 299.7 kWdc / 300.0 kWac solar, and 7.708 MWh usable storage. It serves 478.31 MWh, or 95.66% of annual demand, curtails 122.02 MWh (19.94% of raw renewable generation), records 533 loss-of-load hours and a 157-hour longest deficit, and has $7.25M CAPEX, $11.60M NPC, $0.67M/year EAC, and $1.39 per served kWh. No saved 99% Shamshi design is available. The saved dispatch CSV provides the authoritative hourly example.

## Final Results

The release integrates the seven-site registry, a featured Shamshi case, the paired Rodina result, saved planner scenarios, normalized comparison controls, and downloadable user-run outputs. Public summaries use decision-scale precision.

## Reproducibility

Run `uv sync --extra app --extra dev --extra visualization`, then `uv run python scripts/run_final_validation.py`. Benchmark verification uses `uv run python scripts/run_phase12.py --mode verify`. See `docs/reproduce_steppegrid.md` for the authoritative workflow.
