# Phase 11: Rodina sensitivity and robustness analysis

## Purpose and frozen baseline

Phase 11 is a deterministic sensitivity study, not probabilistic uncertainty quantification. Its
bounds are researcher-defined perturbations, not measured confidence intervals, forecasts, or
probability distributions. The nominal case preserves Phase 10: Rodina (51.302445, 70.541645),
2025 ERA5, 8,760 UTC+05:00-aligned hours, 8.02 GWh reconstructed demand, all three existing load
shapes, ERA5-derived shear `alpha=0.2317610498`, fixed Phase 9 hub heights and PV geometry, empty
useful initial battery inventory, deterministic dispatch, scale-aware PV economics, and 95%/99%
annual served-energy targets.

The final nominal portfolios are 131 Bergey Excel 15 turbines, 83 Trina 450/Fronius 100-kW PV
blocks, and four Tesla batteries for 95%; and 319 Bergey turbines, 202 of the same PV blocks, and
six Tesla batteries for 99%.

## Declared scenarios

| Dimension | Low | Nominal | High | Meaning |
|---|---:|---:|---:|---|
| Demand magnitude | 0.90 | 1.00 | 1.10 | Multiplier on each unchanged hourly load shape |
| Wind shear alpha | 0.18540883984 | 0.2317610498 | 0.27811325976 | Physical wind-model input; sensitivity only |
| PV AC output | 0.90 | 1.00 | 1.10 | Aggregate nonnegative unit-trace multiplier |
| Wind CAPEX | 0.80 | 1.00 | 1.20 | Multiplier on nominal technology CAPEX |
| PV CAPEX | 0.80 | 1.00 | 1.20 | Applied after commercial/utility classification |
| Battery CAPEX | 0.80 | 1.00 | 1.20 | Multiplier on nominal technology CAPEX |

Each primary scenario changes one factor only. Two combined research cases are also reported:
`resource_stress` uses demand 1.10, high shear, and PV 0.90; `resource_favorable` uses demand 0.90,
low shear, and PV 1.10. Economics remain nominal in both. These labels are deterministic case
names, not probability statements.

## Method

Fixed-design robustness dispatches each final Phase 10 portfolio against every scenario and all
three unchanged load shapes. Demand scaling preserves every hourly proportion; PV scaling reuses
the nominal AC trace; low/nominal/high shear traces are regenerated through the Phase 9 turbine
power-curve model. All dispatch conservation tolerances and battery semantics are unchanged.

Demand and PV feasibility boundaries use 30-iteration bounded monotonic searches. Shear behavior
is checked at the declared endpoints and nominal value before a threshold is estimated. Because
ERA5 wind is referenced at 100 m while every fixed turbine hub is below 100 m, higher alpha lowers
modeled hub-height wind. Performance is monotonically decreasing with alpha here, so the useful
boundary is the *maximum* feasible alpha; the requested minimum is simply the declared lower bound.

Economic cases re-rank the union of unique saved robust Phase 10 candidates without physical
redispatch. When a fixed design fails, the same saved-candidate union is selectively replayed under
that physical scenario. This is saved-candidate reselection/replay within the declared Phase 10
candidate set. Every adapted result is labeled “least-cost feasible design among the saved Phase
10 candidate set”; it is not a globally optimized perturbed-scenario design. No full Phase 10
re-optimization is run.

## Fixed-design results

The table reports the binding (worst) load profile; unmet energy is in MWh.

| Scenario | 95% served | Binding | Unmet | LOLH | Longest h | Pass | 99% served | Binding | Unmet | LOLH | Longest h | Pass |
|---|---:|---|---:|---:|---:|:---:|---:|---|---:|---:|---:|:---:|
| nominal | 95.038% | residential | 397.99 | 532 | 41 | yes | 99.003% | residential | 79.99 | 109 | 16 | yes |
| demand low | 96.084% | residential | 282.65 | 420 | 41 | yes | 99.203% | residential | 57.52 | 94 | 15 | yes |
| demand high | 93.683% | residential | 557.24 | 689 | 45 | no | 98.804% | residential | 105.51 | 128 | 17 | no |
| shear low | 95.711% | residential | 343.98 | 466 | 41 | yes | 99.127% | flat | 70.00 | 97 | 17 | yes |
| shear high | 94.282% | residential | 458.60 | 610 | 41 | no | 98.899% | residential | 88.31 | 120 | 16 | no |
| PV low | 94.506% | residential | 440.59 | 594 | 45 | no | 98.896% | residential | 88.55 | 120 | 17 | no |
| PV high | 95.423% | residential | 367.10 | 493 | 41 | yes | 99.108% | residential | 71.52 | 102 | 15 | yes |
| any CAPEX case | 95.038% | residential | 397.99 | 532 | 41 | yes | 99.003% | residential | 79.99 | 109 | 16 | yes |
| resource stress | 91.706% | residential | 731.66 | 909 | 48 | no | 98.551% | residential | 127.80 | 145 | 17 | no |
| resource favorable | 96.860% | residential | 226.62 | 337 | 39 | yes | 99.455% | flat | 39.37 | 64 | 14 | yes |

CAPEX-only cases have identical dispatch. Their CAPEX, NPC, EAC, and cost per served kWh are
nevertheless recomputed. The binding profile remains residential except for the 99% low-shear
case, where flat-within-month becomes marginally binding. Full per-profile energy, reliability,
battery, economics, and conservation fields are in `fixed_design_sensitivity.csv`.

## Robustness margins and load shape

The 95% design meets target through a demand multiplier of 1.00322 (about +0.32%) and down to a PV
multiplier of 0.99078 (about -0.92%). Its maximum feasible shear exponent in the tested interval is
0.234401. The 99% design reaches 1.00148 demand (about +0.15%), 0.99748 PV (about -0.25%), and
maximum alpha 0.232857. Both designs therefore have little nominal margin.

The cost-minimized nominal portfolios therefore have very small reliability headroom. The 99%
nominal design falls below 99% under every tested adverse one-factor physical perturbation:
demand +10%, PV output -10%, and high shear. The declared ranges are deterministic research
scenarios, not confidence intervals or probability distributions.

Across the one-factor physical cases, residential-like demand is normally binding; the noted 99%
low-shear case changes to flat-within-month. The machine-readable load-shape output reports the
best/worst served-fraction spread and ranges in LOLH and longest deficit for every scenario. The
single-profile comparison comes directly from the `flat_within_month`, `residential_like`, and
`community_facility_like` entries in Phase 10's `scale_aware_energy_optima.json`; the minimum NPC
across those three is compared with the matching `robust_all_profiles` entry. Its final label is
“saved Phase 10 single-profile candidate-set comparison.” On that basis, the robust portfolio has
an NPC premium of 10.34% at 95% and 6.91% at 99%. This is conditional on the saved Phase 10 search,
not a universal value of robustness.

## Saved-candidate reselection and economics

All six CAPEX perturbations retain the same equipment mix at both targets within the saved
candidate set. At 95%, NPC ranges are: wind $45.934M-$52.821M, PV $47.004M-$51.751M, and battery
$46.291M-$52.464M. At 99% they are: wind $97.400M-$114.171M, PV $100.008M-$111.563M, and battery
$101.155M-$110.416M. Wind CAPEX has the largest normalized saved-candidate least-cost NPC effect
under these declared ranges; this says nothing about which input is most uncertain.

For 95%, demand-high, PV-low, and combined stress are rescued within the saved set by the nominal
99% portfolio (319 Bergey, 202 Trina450/Fronius blocks, six Tesla; 4,976.4 kW wind, 20,179.8 kWdc,
20,200 kWac PV, 23,124 kWh usable storage; nominal NPC $105.785M). Their worst served fractions are
98.804%, 98.896%, and 98.551%. High shear selects a PV-only saved candidate: 201
Trina460/Fronius blocks and six Tesla units (20,063.82 kWdc, 20,100 kWac, 23,124 kWh), serving
95.022% with 492 LOLH, a 21-hour longest deficit, $39.889M CAPEX, $60.295M NPC, and $3.463M EAC.

No saved candidate meets 99% under demand-high, PV-low, high-shear, or combined-stress conditions.
This is a bounded-candidate result and triggers a documented limitation, not proof of physical
infeasibility. A fresh Phase 10-scale optimization was deliberately not launched because Phase 11's
performance hierarchy prioritizes the saved explored set and prohibits blind repeated searches.

## Sensitivity ranking

For both fixed designs, the normalized served-fraction ranking is demand magnitude first, PV
output second, and wind shear third. For saved-candidate least-cost NPC, wind CAPEX ranks first, followed by PV CAPEX and
battery CAPEX at 99%; at 95%, wind is first, battery second, and PV third. Rankings are descriptive
only over the declared input ranges and do not imply independent random variables or rank actual
uncertainty.

## Scientific audit and limitations

No Phase 9/10 correctness bug or conservation failure was found. Nominal Phase 11 reproduces Phase
10 served fractions, CAPEX, and NPC exactly. The key numerical concern is extremely small target
headroom, especially at 99%. The direction of shear sensitivity is easy to misread: increasing
alpha is adverse because every modeled hub height is below the 100 m ERA5 reference. The combined
stress/favorable labels now follow that physical direction.

ERA5 is not site-measured weather; shear is ERA5-derived rather than mast-measured; demand is
reconstructed rather than measured hourly demand; only one weather year is used; sensitivity bounds
are research scenarios rather than confidence intervals; and no probability distributions are
inferred. The model still omits wakes, land/layout, detailed degradation, snow, soiling, grid power
flow, and Shamshi optimization without real demand. No Monte Carlo, stochastic optimization,
additional equipment, hub-height/geometry optimization, backup generation, grid exchange, or new
reliability target is introduced.

## Reproduction and outputs

Run `.venv\\Scripts\\python.exe scripts\\run_phase11.py` for a complete reproduction. The targeted
combined-scenario correction is reproducible with `--combined-only`. Outputs are written under
`outputs/benchmarks/rodina/phase11/`: fixed sensitivity, candidate-reselection sensitivity and
status CSVs, robustness margins, load-shape robustness, sensitivity rankings, the JSON summary,
and four plots.
