# SteppeGrid Phase 17 — Cross-Village Analysis

## Research question
How do modeled renewable resources affect normalized microgrid composition, reliability, storage, curtailment, and planning cost across seven selected Kazakhstan settlements?

## Cohorts
The primary cohort is Katon-Karagay, Kegen, Shayan, Sai-Otes, and Togyzkuduk using KZ_RURAL_PROXY_V1. Rodina and Shamshi are contextual because their demand bases differ.

## Demand provenance
| Site | Demand basis |
|---|---|
| Rodina | SOURCE_RECONSTRUCTED |
| Shamshi Kaldayakova | SYNTHETIC_ESTIMATE |
| Katon-Karagay | PROXY_DERIVED |
| Kegen | PROXY_DERIVED |
| Shayan | PROXY_DERIVED |
| Sai-Otes | PROXY_DERIVED |
| Togyzkuduk | PROXY_DERIVED |

## Standardized methodology
All scenarios use cached 2025 ERA5, 8,760 hours, Planner V2, scale-aware Planner V2 economics, the full verified catalog, deterministic dispatch, and 95%/99% annual energy served targets.

## Resource characterization
Within the primary cohort, Kegen has the highest modeled PV specific yield and Togyzkuduk the highest representative wind capacity factor.

## 95% and 99% results
See `optimization_results.csv` and `normalized_metrics.csv` for complete designs, energy balances, reliability, economics, search statistics, and hashes.

## Normalized comparison
At 95%, Kegen has the lowest NPC per annual kWh of registered demand; Katon-Karagay has the greatest storage MWh/GWh in the primary cohort.

## Reliability-cost escalation
Within the primary cohort, the greatest modeled NPC increase from 95% to 99% occurs at Sai-Otes (77.4%).

## Contextual interpretation
Rodina uses source-reconstructed literature demand. Shamshi uses its registered synthetic planning estimate. Neither is pooled into proxy-cohort claims.

## Limitations
One ERA5 year; proxy demand for five sites; synthetic Shamshi demand; reconstructed Rodina demand; shared deterministic proxy profile; no wake/layout or grid power flow; no multi-year variability; reference economics; bounded discrete catalog; seven selected settlements are not representative of all Kazakhstan villages.

## Reproducibility
Run `python scripts/run_phase17.py --verify`. Use `--execute` only to rerun missing standardized scenarios.
