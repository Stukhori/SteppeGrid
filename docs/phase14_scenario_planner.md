# Phase 14: interactive scenario planner

> Historical-version note: Phase 14 is frozen. Its reproduction script now pins `RODINA_FROZEN_V1` and `PHASE10_FROZEN_ECONOMICS_V1`. Phase 15 planning scenarios use the separately versioned Planner V2 path described in `docs/phase15_scale_aware_catalog.md`; no Phase 14 or Rodina output is retrofitted.

## Scope and scientific boundary

Phase 14 adds a user-driven planning workflow without changing the frozen Rodina Phase 9–12 benchmark results. `Explore Benchmark` continues to read those frozen artifacts. `Plan a System` creates isolated, hashed user scenarios under `outputs/scenarios/` and invokes computation only after the user presses **Run Planner**.

A planning result is a deterministic model result under declared inputs. It is not a field-validated optimum, procurement quote, confidence interval, probability distribution, or deployment recommendation. Annual served-energy fraction is not uptime.

## Architecture

The typed flow is:

```text
PlanningScenario
  -> PlanningDemand
  -> cached/fetched Open-Meteo ERA5 WeatherDataset
  -> Phase 9 wind and PV unit traces
  -> generalized Phase 10 staged sizing
  -> PlanningResult + hourly dispatch
  -> isolated JSON/CSV artifacts and Streamlit views
```

`steppegrid/planning/models.py` defines the public scenario, demand, design, reliability, economics, and result contracts. UI code does not implement wind, PV, battery, dispatch, or cost equations.

## Demand modes and provenance

The planner supports:

- Rodina benchmark demand: the unchanged Phase 6/9 monthly-row reconstruction and any of the three existing deterministic shapes.
- Estimated annual demand: an explicit annual kWh value distributed over one deterministic shape.
- Estimated monthly demand: 12 explicit monthly kWh totals, each conserved exactly during hourly reconstruction.
- Hourly CSV: exact columns `timestamp,demand_kwh`, where demand is kWh per hourly interval.

Uploads require timezone-aware ISO-8601 timestamps, a consecutive hourly sequence, exactly 8,760 or 8,784 records, and finite nonnegative demand. Duplicate or missing timestamps, NaN/infinity, wrong columns, or invalid lengths are rejected; serious gaps are not interpolated.

Every demand trace carries one source class: `MEASURED`, `SOURCE_REPORTED`, `SOURCE_RECONSTRUCTED`, `PROXY_DERIVED`, `SYNTHETIC_ESTIMATE`, or `USER_PROVIDED`. A separate descriptive confidence label is visible in review/results. These labels are qualitative provenance categories, not numeric confidence scores. The optimizer uses the numeric trace identically regardless of its evidence class.

No defensible Shamshi demand magnitude was found in the repository. Consequently, the application contains no Shamshi default. Shamshi planning requires an explicit annual estimate, 12 monthly totals, a documented proxy, or an hourly upload. Results are labeled **estimated-demand planning scenario**, never a validated Shamshi field optimum.

## Weather and physical-model generalization

Planning weather uses the existing Open-Meteo historical provider with ERA5 and the existing SHA-256 cache convention. The review stage checks cache availability without fetching. An absent exact cache is fetched only during an explicit planning run. Scenario/result provenance records coordinates, model, period, fixed site offset, cache key, and cache status. ERA5 is gridded reanalysis, not an on-site station.

The Phase 9 PV function now accepts site latitude/longitude, tilt, azimuth, and display offset while retaining the original Rodina values as defaults. The planning convention is fixed tilt equal to absolute latitude and equator-facing azimuth. Wind continues to use the two-height ERA5-derived shear estimate and the existing certified/reference curves. This shear is not site measured. Regression tests prove the explicit Rodina parameters and old default call produce identical Phase 9 PV metadata and traces.

## Optimizer reuse and bounds

The planner reuses Phase 10's unit-trace scaling, annual-energy pruning, adaptive energy-share rays, renewable trace cache, dispatch cache, and monotonic battery search. It ranks feasible designs with the unchanged Phase 10 economics. For deliberately small renewable spaces (at most 2,500 portfolios), it uses exact enumeration as a validation-safe first stage; larger interactive cases use the generalized Phase 10 staged rays. This is not a second simplified UI optimizer.

Bounds are deterministic and scenario-aware:

- wind/PV upper count = ceiling of three times annual demand divided by unit annual generation;
- storage ceiling = at least four units and enough nominal search room for two average-demand days, capped at 64 units;
- any renewable count above 25,000 is rejected;
- estimated staged dispatch work above 60,000 evaluations is rejected;
- supported annual demand is 10,000–20,000,000 kWh/year;
- targets are exactly 0.95 and 0.99 annual served energy.

The bounds control the interactive MVP; they do not prove global optimality for a staged real-size search. Exact reduced-space tests compare wind-only, PV-only, and hybrid cases against brute force. A forced staged monotonic ray is also checked against brute force.

## UI workflow and state

The workflow is `Site -> Demand -> Reliability -> Technology -> Review -> Results`. Review shows annual/peak/average-related demand diagnostics, load factor, monthly energy, a representative hourly trace, evidence class, confidence label, scenario hash, and weather-cache state. Normal navigation never optimizes. Changing any hashed input marks a previous result stale. Completed results can be compared within the Streamlit session.

Results show selected counts/capacities, served fraction, LPSP-related quantities, LOLH, longest and maximum deficit, curtailment, CAPEX, NPC, EAC, planning cost per served kWh, and hourly demand/generation/SOC/unmet/curtailment views.

## Outputs and reproducibility

Each scenario is written only to:

```text
outputs/scenarios/<scenario_id>/
  scenario.json
  result.json
  reliability.csv
  dispatch.csv
  provenance.json
```

The deterministic `scenario_id` derives from the canonical scenario input SHA-256. Exports retain the demand hash, weather cache key and period, source classifications, software version, design, reliability, economics, and per-file SHA-256 values. They never write into `outputs/benchmarks/rodina/`.

## Reproduction and measured performance

Launch the application:

```powershell
python -m pip install -e ".[app]"
streamlit run app.py
```

Run the documented Shamshi example with its estimate explicitly supplied:

```powershell
python scripts/run_phase14_example.py --annual-kwh 500000 --target 0.95
```

On the Phase 14 development machine, a small cached 10,000 kWh/year case measured 0.04 s demand review, 0.60 s weather/generation preparation, 1.16 s optimizer time, 0.04 s detailed dispatch preparation, 1.87 s before export, and 2.07 s total wall time. The final representative cached 500,000 kWh/year reproduction measured 0.03 s, 0.55 s, 2.27 s, 0.04 s, 3.00 s, and 3.19 s for the same stages. Timings are observations, not promises. The demand magnitudes are explicit example assumptions—not observed or source-backed Shamshi demand.

The run selected 67 SD6 turbines (348.4 kW), 6 Trina/SMA PV blocks (299.7 kWdc / 300.0 kWac), and 2 Tesla Megapacks (7,708 kWh usable). It served 95.6618% of modeled demand, with 21,691.12 kWh unmet, 533 loss-of-load hours, a 157-hour longest deficit, and 122,015.71 kWh curtailed. Reference-planning CAPEX was $7,246,929, NPC $11,595,164, and EAC $665,885.58/year.

## Current limitations

The workflow uses one weather year, fixed-offset timezones, deterministic load shapes, no wake/layout model, no grid power flow, no diesel or market tariff model, and reference rather than Kazakhstan bid costs. Session comparison is not a database. Custom-site weather may require internet access on the first explicit run. No Phase 15 functionality is included.
