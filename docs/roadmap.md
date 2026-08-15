# Roadmap

## Phase 0: simulation foundation

- Typed and aligned hourly domain inputs.
- Generic empirical wind power curve.
- Transparent initial PV and battery models.
- Renewable-first dispatch and explicit energy accounting.
- Grid outage intervals and primitive outage metrics.
- Synthetic demo and deterministic tests.
- Methodology and assumptions register.

## Phase 1: trustworthy data interfaces

- [x] Add load provenance, evidence-quality classification, and strict CSV ingestion.
- [x] Add total and critical hourly load with deterministic synthetic providers.
- [x] Add primitive total and critical outage-service metrics.
- [x] Add a literature-derived monthly benchmark with source-integrity reporting.
- [x] Add deterministic monthly-to-hourly reconstruction and shape sensitivity.
- [x] Pair Rodina reconstructions with a verified site anchor and timezone-correct ERA5 year.
- [x] Add raw resource-demand timing diagnostics for all Rodina hourly assumptions.
- Validate the cached Open-Meteo ERA5 provider against independent data.
- Enforce timezone-aware timestamps in every legacy/internal constructor; CSV load already does.
- Establish validated Kazakhstan weather sources and location metadata.
- Add dataset licenses, citations, uncertainty, and quality flags.
- Add a scientifically justified 10 m wind to turbine hub-height adjustment.
- Add direct `CopernicusERA5LandProvider` access for independent validation and citation.

## Phase 2: model validation

- Compare the PV model with a maintained, validated solar library.
- Add hub-height wind-speed conversion only with site roughness and measurement metadata.
- Validate battery behavior against selected equipment specifications.
- Add grid import/export limits, tariffs, and time-varying carbon intensity.
- Track stored-energy provenance for defensible renewable-fraction reporting.
- Add regression fixtures from source-attributed field or benchmark data.
- Apply the pilot-site workflow to a user-supplied rural Kazakhstan village and review the annual report.

## Phase 3: scenario analysis

- Introduce a dispatch-policy interface and compare documented strategies.
- Support scheduled and reproducible stochastic outage scenarios.
- Add cost and emissions calculations with dated configurable inputs.
- Report uncertainty and sensitivity rather than only point estimates.
- Evaluate conventional and HelixGen turbines using comparable empirical curves.

## Phase 4: services and optimization

- Add a FastAPI boundary around the stable simulation contracts.
- Add sizing optimization with explicit objectives, constraints, and reproducibility.
- Build a Next.js and TypeScript application after the scientific API stabilizes.
- Add geographic selection only after spatial data provenance and resolution are defined.

Authentication, billing, social features, live sensor streaming, and machine learning are outside the current scope.
