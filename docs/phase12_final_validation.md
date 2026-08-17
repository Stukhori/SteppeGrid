# Phase 12: final Rodina validation and synthesis

## Scope

Phase 12 validates, reproduces, and consolidates the frozen Phase 9–11 Rodina study. It adds no
new model, scenario, equipment, target, or optimization. Rodina hourly demand remains a
deterministic reconstruction from published monthly electricity consumption, not a measured
interval dataset. The 2025 weather carrier remains cached ERA5 gridded reanalysis.

## Validation modes

`verify` is the lightweight default. It loads the cached weather and reconstructed loads, checks
8,760-hour integrity, hashes inputs, cross-checks frozen outputs, validates Phase 11 directions and
semantics, and regenerates the final tables, figures, manifest, audit, and report.

`reproduce` additionally executes the frozen Phase 9 physical benchmark and independently
dispatches the two selected Phase 10 portfolios. It checks wind output/capacity factors,
representative PV energy/POA/yield/clipping, battery benchmark values, selected-design reliability,
and final economics. It does not rediscover an optimizer solution or run a Phase 10 search.

## Provenance and claims discipline

The assumption registry distinguishes source-reported, source-reconstructed, ERA5-derived,
manufacturer/certification, modeling-assumption, research-sensitivity, optimized-decision, and
derived-result fields. In particular:

- 7.72 GWh is the paper's printed annual load.
- 8.02 GWh is reconstructed from its published monthly rows and is used in optimization.
- `alpha=0.2317610498` is ERA5-derived, not mast-measured.
- Phase 11 ranges are deterministic research scenarios, not confidence intervals.
- Candidate reselection means least-cost feasible within the saved Phase 10 candidate set, not a
  global perturbed-scenario optimum.
- 95% and 99% describe annual load energy served, not uptime.

## Final interpretation

The final cost-minimized designs have little headroom: approximately +0.32% demand for the 95%
design and +0.15% for the 99% design. The nominal 99% design fails its target under every tested
adverse one-factor physical perturbation. Moving from 95% to 99% requires substantially more wind,
PV, storage, lifecycle cost, and curtailment. That overbuild is a deterministic isolated-system
response to temporal and seasonal mismatch with finite storage; curtailment is not automatically a
software defect.

Residential-like load is generally binding. The robust-versus-single-profile result retains its
Phase 11 label, “saved Phase 10 single-profile candidate-set comparison,” and is sourced from the
profile modes and `robust_all_profiles` entries in `scale_aware_energy_optima.json`.

## Audit decision

Phase 12 may declare completion only when `validation_audit.json` contains zero blockers. Warnings
represent documented scope limitations, not silently relaxed tests.

## Limitations registry

- Data: reconstructed rather than measured hourly demand; 7.72/8.02 GWh source discrepancy;
  ERA5 rather than site meteorology; one weather year.
- Wind: ERA5-derived shear; no wakes, layout, or land constraints; declared high-wind extension.
- PV: no detailed snow, soiling, or long-term degradation; simplified inverter treatment.
- Storage: no electrochemical degradation; reference economics rather than procurement quotes.
- Optimization: bounded discrete search, fixed hub heights/orientation/dispatch; energy targets are
  not uptime standards.
- Sensitivity: deterministic perturbations, not probabilities, confidence intervals, or Monte
  Carlo uncertainty quantification.
- Field case: Shamshi demand is unavailable, so no Shamshi optimal system is reported.
