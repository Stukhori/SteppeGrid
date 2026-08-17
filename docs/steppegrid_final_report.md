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

The interface consumes fourteen frozen standardized Planner V2 scenarios and normalizes capacity and cost by registered annual demand. The primary five-site proxy cohort is analyzed separately from Rodina and Shamshi. Kegen has the highest proxy-cohort PV specific yield; Togyzkuduk has the highest representative wind capacity factor; Sai-Otes has the largest proxy-cohort 95%→99% NPC escalation.

## My Village — Shamshi Kaldayakova

Shamshi Kaldayakova (Aktobe Region) is the featured blue `MY VILLAGE` case. Its current registered demand is 0.50 GWh/year. Cached weather contains 8,760 modeled hours. The standardized 95% system uses 200 kW wind, 347.8 kWdc / 350 kWac solar, and 1.028 MWh usable storage. It serves 479.13 MWh, or 95.83% of annual demand, curtails 281.84 MWh (36.61% of raw generation), records 549 loss-of-load hours and a 139-hour longest deficit, and has $1.84M CAPEX, $2.64M NPC, $0.15M/year EAC, and $0.316 per served kWh. The 99% system uses 500 kW wind, 298.1 kWdc / 300 kWac solar, and 1.542 MWh storage; it serves 99.12% with $4.22M NPC. Saved dispatch CSVs provide the authoritative hourly examples.

## Final Results

The release integrates the seven-site registry, a featured Shamshi case, the paired Rodina result, saved planner scenarios, normalized comparison controls, and downloadable user-run outputs. Public summaries use decision-scale precision.

## Reproducibility

Run `uv sync --extra app --extra dev --extra visualization`, then `uv run python scripts/run_final_validation.py`. Benchmark verification uses `uv run python scripts/run_phase12.py --mode verify`. See `docs/reproduce_steppegrid.md` for the authoritative workflow.
