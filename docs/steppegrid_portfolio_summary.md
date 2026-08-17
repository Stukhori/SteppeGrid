# SteppeGrid — Portfolio Summary

SteppeGrid is a renewable microgrid planning platform built for rural Kazakhstan. It converts a village’s electricity demand and hourly weather into modeled wind and solar generation, then simulates battery dispatch hour by hour. A discrete optimizer searches supported equipment combinations and reports annual energy served, deficit timing, curtailment, and lifecycle planning cost.

The v1.0 application covers seven real settlements: Rodina, Shamshi Kaldayakova, Katon-Karagay, Kegen, Shayan, Sai-Otes, and Togyzkuduk. Each has a typed site record, repository-relative weather cache, active annual demand, and reproducibility metadata. A Streamlit interface provides an overview, village map and detail view, normalized site comparison, an interactive planner, physical-model views, reliability, economics, sensitivity, and a concise explanation of the workflow.

The project’s main technical work includes hourly time-series alignment, wind power-curve modeling, PV and inverter modeling, battery state-of-charge dispatch, energy-based reliability accounting, deficit-event analysis, staged discrete optimization, scale-aware equipment selection, lifecycle economics, and hash-backed scenario export. Normal page views use saved artifacts for responsive deployment; only explicit user planner runs optimize.

The frozen Rodina Benchmark demonstrates the reliability–cost tradeoff. Its 95% design uses 2.04 MW wind, 8.30 MWac solar, and 15.42 MWh storage at $49.4M NPC. Reaching 99% annual energy served increases the selected capacities to 4.98 MW wind, 20.20 MWac solar, and 23.12 MWh storage, with $105.8M NPC.

## My Village — Shamshi Kaldayakova

Shamshi is the featured personal village case and carries a consistent blue `MY VILLAGE` identity. Its current planning demand is 0.50 GWh/year. The standardized 95% system uses 200 kW wind, 347.8 kWdc solar, and 1.03 MWh storage; it serves 95.83% of annual electricity at $2.64M NPC. The 99% scenario uses 500 kW wind, 298.1 kWdc solar, and 1.54 MWh storage, serving 99.12% at $4.22M NPC.

SteppeGrid’s central design choice is separation: the product interface is clear and decision-focused, while classifications, hashes, source metadata, methodology versions, and frozen audit records remain available internally. This lets future field datasets replace current inputs without rebuilding the software architecture.
