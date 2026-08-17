# Phase 17 — Cross-Village Analysis

## 1. Research question

How do modeled renewable-resource conditions affect the normalized cost, composition, reliability, storage requirement, and curtailment of optimized wind–PV–battery systems across seven selected Kazakhstan settlements?

## 2. Sites

The analysis covers Rodina, Shamshi Kaldayakova, Katon-Karagay, Kegen, Shayan, Sai-Otes, and Togyzkuduk.

## 3. Demand provenance

| Site | Analytical role | Demand basis |
|---|---|---|
| Katon-Karagay | Primary cohort | KZ_RURAL_PROXY_V1 |
| Kegen | Primary cohort | KZ_RURAL_PROXY_V1 |
| Shayan | Primary cohort | KZ_RURAL_PROXY_V1 |
| Sai-Otes | Primary cohort | KZ_RURAL_PROXY_V1 |
| Togyzkuduk | Primary cohort | KZ_RURAL_PROXY_V1 |
| Rodina | Contextual | Source-reconstructed literature demand |
| Shamshi Kaldayakova | Contextual | Registered synthetic planning estimate |

## 4. Standardized methodology

All fourteen runs use each site's active registered demand, cached 2025 ERA5 weather, 8,760 hourly intervals, deterministic dispatch, Planner V2, scale-aware Planner V2 economics, and 95% or 99% annual energy served. The optimizer's existing 25,000-unit safety bound makes the three distributed-wind products technically incompatible with the largest standardized demand. The same two scalable Planner V2 turbines—NPS 100C-21 and LTW42 250 kW—are therefore eligible at every site; all nine PV configurations and all four batteries remain eligible. No search limit was changed.

## 5. Resource characterization

A common NPS 100C-21 trace and common Trina 450 W / SMA 50 kW PV block characterize resources independently of selected designs. Within the proxy cohort, Togyzkuduk has the highest representative wind capacity factor (21.04%), while Kegen has the highest PV specific yield (1,903.7 kWh/kWp-year). Kegen's wind CF is lowest (0.42%); Togyzkuduk's PV yield is lowest within the cohort (1,481.3 kWh/kWp-year). Hourly wind/PV correlation is reported as a simple descriptive complementarity indicator.

## 6. 95% results

All seven standardized scenarios are feasible. Katon-Karagay, Kegen, and Shayan select PV-only renewable portfolios under the bounded technology set; Rodina, Shamshi, Sai-Otes, and Togyzkuduk select mixed wind/PV designs. Complete capacities, energy balances, reliability, economics, hashes, and search statistics are in `outputs/phase17/optimization_results.csv`.

## 7. 99% results

All seven 99% scenarios are feasible. Higher reliability changes both scale and composition; the response is not a uniform multiplier of the 95% design.

## 8. Normalized comparison

`normalized_metrics.csv` reports wind MW/GWh, PV MWac/GWh, battery MWh/GWh, cost per annual kWh of demand, overbuild, curtailment, unmet fraction, and wind/PV generation shares. These are planning normalization metrics, not electricity tariffs.

## 9. Reliability-cost escalation

Across the proxy cohort, NPC increases range from 13.35% at Kegen to 77.36% at Sai-Otes when moving from 95% to 99%. Storage escalation ranges from 1.59% at Shayan to 177.78% at Sai-Otes. Zero-technology denominators are represented with absolute changes and entry flags instead of infinite percentages.

## 10. Proxy-cohort findings

- Togyzkuduk has the strongest representative wind CF; Kegen has the strongest modeled PV yield.
- Katon-Karagay and Kegen's very weak representative wind traces correspond with PV-only selected renewable portfolios.
- Resource strength alone does not determine storage or cost: temporal alignment, curtailment, discrete equipment, and the reliability target also matter.
- Sai-Otes experiences the largest proxy-cohort NPC and storage escalation from 95% to 99%.

## 11. Rodina and Shamshi context

Rodina is a standardized Planner V2 scenario, not a replacement for the frozen benchmark. Its literature-reconstructed demand differs from the proxy methodology. Shamshi uses its current 0.50 GWh/year synthetic planning estimate and is not field validation. Both appear for context but are excluded from primary-cohort claims.

## 12. Limitations

The study uses one ERA5 year; proxy demand for five sites; synthetic Shamshi demand; reconstructed Rodina demand; a shared deterministic proxy profile; no wake/layout or grid power flow; no multi-year variability; reference planning economics; and a bounded discrete equipment catalog. Seven selected settlements are not statistically representative of Kazakhstan.

## 13. Reproducibility

```bash
uv run python scripts/run_phase17.py --verify
```

Use `--execute` only to generate missing scenario checkpoints. Existing standardized results are reused.
