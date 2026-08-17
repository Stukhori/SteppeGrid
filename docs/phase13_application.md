# Phase 13 interactive planning application

Phase 13 adds a Streamlit application over the frozen Phase 9–12 Rodina benchmark. It does not
change the scientific model, rerun optimization, or add a Shamshi result. The interface is a
research-results explorer, not an investment or equipment-selection tool.

## Run locally

Install the application extra and start Streamlit from the repository root:

```powershell
python -m pip install -e ".[app]"
streamlit run app.py
```

The app validates required Phase 11 and Phase 12 artifacts at startup. If an artifact is missing,
it gives a readable error and the verification command:

```powershell
python scripts/run_phase12.py --mode verify
```

## Architecture and safeguards

- `app.py` contains presentation and interaction only.
- `steppegrid/app/data.py` is the read-only frozen-artifact repository.
- `steppegrid/app/services.py` is the application service boundary. It exposes the two frozen
  robust designs, validated tables, provenance, and a cached hourly replay.
- `steppegrid/app/charts.py`, `formatting.py`, and `state.py` hold view helpers and vocabulary.
- The hourly explorer scales frozen Phase 9 unit traces for a frozen Phase 10 design and replays
  existing battery behavior. Its annual unmet energy is checked against the established Phase 10
  dispatch aggregate before display.
- No UI control changes equipment counts, scientific assumptions, or optimization bounds.

The data flow is `frozen artifacts and local traces → repository → planning service → chart-ready
data → Streamlit UI`. JSON/CSV reads use a process-local cache, model-input reconstruction is lazy
and cached once, Streamlit caches the service resource, and each final-design/profile dispatch frame
is cached independently. Navigation never triggers network weather access or an optimizer search.

## Pages

The eight views are Overview, Demand & Weather, Renewable Generation, System Design, Reliability,
Economics, Sensitivity, and Methodology & Provenance. Together they expose the frozen summary,
published-demand discrepancy, three reconstructed load shapes, cached weather, supported equipment,
both selected designs and their cost/reliability tradeoff, an hourly dispatch explorer, corrected
Phase 11 scenarios and margins, and the Phase 12 assumptions/provenance audit.

## Testing

Application tests verify exact final-design loading, sensitivity directions and margin values,
candidate-reselection terminology and single-profile provenance, unit formatting, missing-artifact
errors, and an 8,760-hour dispatch replay against the frozen aggregate. Streamlit's application test
runtime is also used to smoke-test every navigation route.

Rodina hourly demand is a deterministic reconstruction of published monthly energy, not measured
hourly demand. The three profiles are load-shape assumptions that preserve the same 8.02 GWh annual
total. ERA5 is gridded reanalysis rather than local station data. Annual served-energy fraction is
not uptime.

Sensitivity bounds are deterministic research scenarios, not confidence intervals or probability
distributions. Adaptive Phase 11 results mean the least-cost feasible design among the saved Phase
10 candidate set: `saved_phase10_candidate_reselection`; no full perturbed-scenario re-optimization
was performed. Because modeled hub heights are below the 100 m ERA5 reference, increasing wind-shear
alpha lowers hub-height wind and is adverse.

The robust-versus-single-profile comparison is loaded directly from
`outputs/benchmarks/rodina/phase10/scale_aware_energy_optima.json`, covering the three saved
single-profile modes and `robust_all_profiles` using net present cost. Its final label remains
“saved Phase 10 single-profile candidate-set comparison.”

Shamshi remains unavailable: measured electricity-demand data are pending and no Shamshi
optimization is reported.

Remaining scope limits include one weather year, reconstructed rather than measured demand, no
wake/layout/degradation/grid-physics extensions, and planning-reference costs rather than bids.
Phase 13 introduces no new scientific methodology.
