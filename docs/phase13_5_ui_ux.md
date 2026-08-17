# Phase 13.5 UI/UX redesign

Phase 13.5 turns the functional Streamlit MVP into a coherent analytical product while preserving
the frozen Phase 9–12 scientific pipeline and all Phase 13 capabilities. It introduces no new
scientific methodology, optimization, sensitivity scenarios, or field-case claims.

## Design direction

The interface uses a restrained infrastructure/research visual language: warm neutral surfaces,
dark green identity color, compact borders, limited rounding, and high-contrast semantic colors.
Wind, solar, storage, unmet energy, curtailment, success, caution, and critical states retain the
same colors on every page. Information hierarchy progresses from research interpretation to key
metrics, interactive charts, and optional detailed tables.

The Streamlit theme is configured in `.streamlit/config.toml`. Global tokens and responsive CSS are
centralized in `steppegrid/app/theme.py`; page modules do not carry their own style blocks.

## Component system

`steppegrid/app/components.py` supplies reusable page headers, badges, section headers, metric cards
with glossary help, equipment and design cards, scientific callouts, site-status cards, workflow and
annual-energy flows, comparison tables, audit summaries, limitations, and compact sidebar status.
These components are presentation-only and receive values from the application service.

`steppegrid/app/charts.py` is the single interactive chart layer. It uses Altair, already installed
with Streamlit, and applies the semantic palette, hover tooltips, explicit units, readable legends,
and threshold/status encoding. Pass/fail charts include text as well as color.

## Navigation and interaction

The sidebar groups the existing eight pages into Study, Planning, Analysis, and Research. Rodina and
Shamshi status remain globally visible but compact. `Explore Benchmark` is the only active product
mode; Phase 14 planning is identified as unavailable and has no fake control.

Target controls use a visible 95%/99% segmented selector. Load profiles, equipment, sensitivity
scenarios, tabs, and date windows retain their selection through normal Streamlit session state.
The dispatch explorer provides computed first-week, longest-deficit-event, and highest-curtailment
windows plus a custom date range. Raw hourly tables are collapsed by default.

## Page hierarchy

- **Overview:** benchmark hero, evidence badges, Rodina/Shamshi status, high-value design cards,
  the reliability-cost finding, frozen comparison, and workflow.
- **Demand & Weather:** separated tabs, the 7.72/8.02 GWh provenance card, profile selection,
  interactive monthly/hourly views, and weather-specific tabs.
- **Renewable Generation:** analytical equipment cards, separate wind energy/capacity-factor charts,
  PV block selection, and selected unit traces.
- **System Design:** prominent target selection, wind/solar/storage architecture cards, annual flow,
  95%/99% comparison, and coordinated dispatch charts.
- **Reliability:** plain-language interpretation first, glossary-backed metrics, cross-profile
  comparison, computed deficit events, duration distribution, and longest-event view.
- **Economics:** selected-design cost metrics, total cost comparison, and Rodina-specific
  reliability-cost interpretation. No unvalidated component breakdown is invented.
- **Sensitivity:** target threshold, explicit meets/below-target states, scenario inspection, margin
  cards, and deterministic—not probabilistic—wording.
- **Methodology & Provenance:** compact audit status, assumptions grouped into expanders, provenance
  cards, candidate-reselection semantics, and limitations organized by evidence domain.

## Accessibility and responsive behavior

Important states always include labels such as `MEETS TARGET` and `BELOW TARGET`; color is not the
only signal. Controls and charts use descriptive labels and units. Glossary help explains served
energy, LPSP, LOLH, NPC, EAC, curtailment, capacity factor, POA, and binding profile. Contrast is
designed for a light theme. At narrower desktop widths, workflow and flow components collapse to
fewer columns, while Streamlit's native metric/card columns wrap.

## Caching and performance

Frozen CSV/JSON artifacts remain process-cached. The planning service and immutable Phase 9 traces
are loaded lazily and cached. Final-design/profile dispatch frames and their deficit-event summaries
are cached independently. Ordinary navigation does not run Phase 10 optimization, Phase 11
sensitivity generation, or Phase 12 validation. Missing frozen outputs and missing provenance-listed
local ERA5 inputs produce actionable UI messages rather than triggering live weather retrieval.

## Scientific terminology safeguards

Rodina demand is always described as reconstructed, served-energy fraction is never called uptime,
ERA5 weather and shear are not called measured, Phase 11 ranges remain deterministic research
scenarios, and saved-candidate adaptation is not called global re-optimization. Shamshi optimization
remains disabled because real demand is unavailable; Rodina or synthetic demand is not substituted.

## Relationship to Phase 14

The grouped navigation and reusable components can support a future `Plan a System` mode, but Phase
13.5 implements only `Explore Benchmark`. No upload, scenario editor, optimizer control, or Phase 14
workflow exists in this phase.
