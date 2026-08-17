# Phase 15: scale-aware equipment catalog

## 1. Motivation and boundary

Phase 15 expands the equipment choices available to the generalized planner. It does not change ERA5 interpretation, wind-height extrapolation, turbine-curve interpolation, PV irradiance and temperature equations, battery dispatch, dispatch order, energy accounting, or reliability metrics. The Phase 9–12 Rodina benchmark remains frozen.

Two versions make that separation explicit:

- `RODINA_FROZEN_V1` is exactly the equipment set used by the frozen benchmark and the Phase 14 reproduction command.
- `PLANNER_V2` is V1 plus a deliberately small set of verified planning additions.

New scenarios default to `PLANNER_V2` and `PLANNER_SCALE_AWARE_ECONOMICS_V2`. Scenario hashes, result JSON, provenance JSON, CSV downloads, and the UI include both versions. Running Rodina in the planner is a **new planning scenario using Planner V2**, never a corrected Rodina benchmark. Broader catalog coverage does not make a scenario field validated.

## 2. V1 audit and identified gaps

| Category | V1 equipment | Physical increment | Provenance / economics |
|---|---|---:|---|
| Wind | Skystream 3.7 | 2.1 kW; 10.7 m planning hub | SWCC curve + manufacturer manual; one 20-kW-class NREL cost reference |
| Wind | SD6 | 5.2 kW; 9 m planning hub | SWCC curve + manufacturer leaflet; same cost reference |
| Wind | Bergey Excel 15 | 15.6 kW; 30 m planning hub | SWCC curve + manufacturer page; same cost reference |
| PV modules | Trina 450 W, REC 470 W, Trina 460 W | module-level sizing within inverter blocks | manufacturer datasheets |
| PV inverter | SMA CORE1 STP 50-41 | 50 kWac; about 49.7–50.0 kWdc per modeled block | manufacturer datasheet; Phase 10 commercial PV class |
| PV inverter | Fronius Tauro ECO 100 | 100 kWac; about 99.6–99.9 kWdc per modeled block | manufacturer datasheet; Phase 10 commercial PV class |
| Storage | Saft Intensium Max 20 HE LFP | 2,185 kWh usable / 1,100 kW | manufacturer datasheet; generic utility four-hour reference |
| Storage | Tesla Megapack 2-hour | 3,854 kWh usable / 1,927 kW | manufacturer product data; generic utility four-hour reference |

The largest physical gaps were 15.6–250 kW wind and zero storage below 2.185 MWh. A 50 kWac minimum PV block was also coarse for the supported 10–50 MWh/year end of the planner, so one smaller inverter was justified. No additional module was needed: integer strings of the three existing verified modules already size each inverter block closely.

## 3. V2 additions and primary provenance

| Key | Scale | Modeled parameters | Authoritative source |
|---|---|---|---|
| `northern_power_nps_100c_21` | community | 100 kW, 20.7 m rotor, deterministic 37 m hub, 3–25 m/s operation, manufacturer-tabulated 1–25 m/s curve | [Northern Power NPS 100C-21 brochure](https://northernpower.com/wp/wp-content/uploads/2025/11/brochure-NPS-100C-21_ed2020_light_ENG.pdf) |
| `leitwind_ltw42_250` | commercial | 250 kW, 42 m rotor, deterministic 39 m hub, 2.5–20 m/s operation, manufacturer-tabulated curve | [LEITWIND product portfolio](https://www.leitwind.com/wp-content/uploads/2025/08/Leitwind_ProductPortfolio_ENG_Esecutivo-LR_WC_S.pdf) |
| `sungrow_powerstack_st255_2h` | small community | 257 kWh usable/nominal, 125 kW, LFP, 0–100% depth of charge/discharge, 90% deterministic RTE | [Sungrow ST255CS-2H datasheet](https://info-support.sungrowpower.com/datasheet-materials/b4f56963-dbd2-4c43-8cbc-0808eb4cf083.pdf) and [manufacturer product specification](https://www.sungrowpower.com/en/products/c-i-energy-storage-system/st255cs-2h) |
| `sungrow_powerstack_st510_4h` | community | 514 kWh usable/nominal, 125 kW, LFP, 0–100% operating range, 90% RTE | [Sungrow ST510CS-4H specification](https://www.sungrowpower.com/us/en/products/residential-energy-storage-system/st510cs-4h-0708) and [manufacturer manual](https://info-support.sungrowpower.com/product-materials/137cdbea-46d5-4a6f-a017-e851b87088db.pdf) |
| `sma_sunny_tripower_x_25` | small community | 25 kWac, 37.5 kWdc maximum, 98.0% European / 98.2% maximum efficiency, 430–800 V MPPT | [SMA Sunny Tripower X datasheet](https://files.sma.de/downloads/STPxx-50-DS-en-21.pdf) |

No wind curve point is inferred from rated power or digitized from a marketing chart. The NPS table contains negative parasitic values at 1–2 m/s; SteppeGrid records the source note and bounds them to zero below the documented 3 m/s cut-in, consistent with the existing catalog convention. Each battery begins at minimum SOC, hence zero useful initial inventory.

`SMALL_COMMUNITY`, `COMMUNITY`, `COMMERCIAL`, and `UTILITY` are descriptive metadata. They organize the UI and explicit filters; they do not silently exclude equipment based on demand.

## 4. Economics treatment and versioning

`PHASE10_FROZEN_ECONOMICS_V1` retains the exact historical behavior: all wind uses $8,425/kW and all storage uses $482/kWh. `PLANNER_SCALE_AWARE_ECONOMICS_V2` uses deterministic installed-project-scale rules:

- wind at or below 20 kW: $8,425/kW residential distributed-wind class;
- wind above 20 through 100 kW: $6,327/kW commercial distributed-wind class;
- wind above 100 kW: $3,270/kW large distributed-wind class;
- usable storage below 1,000 kWh: $672/kWh commercial standalone BESS class;
- usable storage at or above 1,000 kWh: the frozen $482/kWh utility four-hour reference.

Wind values and the common $39/kW-year O&M come from NREL's [2022 Cost of Wind Energy](https://www.nrel.gov/docs/fy24osti/88335.pdf), in 2022 USD. The commercial battery class uses NREL's [Q1 2022 PV and storage cost benchmark](https://www.nrel.gov/docs/fy22osti/83586.pdf), which reports $672/kWh in 2021 USD. SteppeGrid exposes this source base year rather than inventing an escalation factor. This mixed-source-year limitation is explicit in result metadata. These are SteppeGrid planning economic classes, not government standards, Kazakhstan costs, vendor quotes, or procurement estimates. PV retains the existing deterministic commercial/utility rule.

## 5. Optimizer integration and validation

The planner still uses scenario-aware annual-generation bounds, analytical annual-energy pruning, unit-trace scaling, renewable and dispatch caches, monotonic battery search, staged Phase 10 energy-share rays, and deterministic least-NPC ranking. Bounds use each selected unit's actual annual trace; there is no inherited assumption that wind units are about 15 kW. Reduced mixed V1/V2 spaces, including no-storage and both new/old storage choices, match exact brute force in tests.

The full V2 selection is larger but remains bounded. On the cached Shamshi comparison it considered 5 wind models, 9 PV configurations, and 4 batteries; 12,805,620 theoretical combinations were reduced to 2,511 renewable traces and 12,685 dispatch evaluations, with 20,364 cache hits. No heuristic equipment dominance rule was added.

## 6. Required Shamshi expanded-catalog comparison

Both cases use Shamshi Kaldayakova (50.578333, 57.544722), cached 2025 ERA5, a synthetic 500,000 kWh/year community-facility-like profile, and a 95% annual served-energy target. V1 evaluates all original catalog equipment with frozen economics; V2 evaluates all verified V2 equipment with scale-aware economics.

The Phase 14 guide's 67 × SD6 / 6 × Trina-SMA / 2 × Tesla example used an explicit one-model choice in each technology category. The Phase 15 V1 column is intentionally a full-catalog V1 baseline, not a replay of that restricted selection; this makes the V1 and V2 availability rules equivalent (all verified equipment in the selected catalog).

| Quantity | V1 | V2 |
|---|---:|---:|
| Wind | 17 × Bergey Excel 15 | 9 × Bergey Excel 15 |
| Wind capacity | 265.2 kW | 140.4 kW |
| PV | 2 × REC 470 / Fronius 100 kW block | 4 × REC 470 / Fronius 100 kW block |
| PV DC / AC | 199.28 / 200.0 kW | 398.56 / 400.0 kW |
| Storage | 1 × Saft Intensium Max 20 HE | 4 × Sungrow ST255CS-2H |
| Storage energy / power | 2,185 kWh / 1,100 kW | 1,028 kWh / 500 kW |
| Renewable generation | 704,397.69 kWh | 785,036.34 kWh |
| Served fraction | 96.7617% | 95.2463% |
| Unmet energy | 16,191.55 kWh | 23,768.37 kWh |
| LOLH / longest deficit | 399 h / 157 h | 648 h / 138 h |
| Curtailment | 204,467.88 kWh | 299,387.19 kWh |
| CAPEX | $3,684,047.20 | $1,747,738.40 |
| NPC | $5,071,484.70 | $2,522,573.35 |
| EAC | $291,244.57/year | $144,866.02/year |
| Optimizer runtime | 47.65 s | 184.85 s |

V2 materially changes the architecture and modeled cost. The selected wind product remains the V1 Bergey, while the smaller V2 storage unit replaces the multi-MWh minimum and installed wind falls as PV rises. The cost change cannot be attributed to equipment granularity alone because V2 intentionally also applies versioned scale-aware wind and storage economics. Both designs meet the declared target; the different surplus above 95% is a consequence of discrete portfolios and the staged search, not evidence that one catalog is more reliable probabilistically.

The optional small-scenario experiment and optional Rodina V2 comparison were not run. No frozen Rodina output was overwritten.

## 7. Reproduction and machine-readable outputs

```powershell
.\.venv\Scripts\python.exe scripts\run_phase15.py --skip-small
```

This writes `catalog_v2.json`, `equipment_provenance.csv`, `catalog_validation.json`, `shamshi_catalog_comparison.csv`, and `phase15_summary.json` below `outputs/phase15/`. Scenario outputs remain isolated and record both method versions. Generated outputs are ignored by Git; the reproduction code and source records are version controlled.

## 8. Limitations

Phase 15 does not add wake/layout or land modeling, grid power flow, degradation, cycling economics, multi-year weather, stochastic search, demand forecasting, procurement quotes, or field validation. Manufacturer standard-density curves and gridded ERA5 do not establish site performance. Staged real-size search is deterministic and tested against brute force in reduced spaces, but it is not an exhaustive full-space proof. The V2 run's longer runtime is accepted for explicit full-catalog analysis and is reported rather than hidden.
