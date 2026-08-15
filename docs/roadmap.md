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

- Extend the initial weather provenance schema to load and turbine datasets.
- Validate the cached Open-Meteo ERA5 provider against independent data.
- Enforce timezone-aware timestamps and document resampling rules.
- Establish validated Kazakhstan weather sources and location metadata.
- Add critical and non-critical load series without silently deriving either.
- Add dataset licenses, citations, uncertainty, and quality flags.
- Add a normalized load-profile CSV provider with provenance.
- Add a scientifically justified 10 m wind to turbine hub-height adjustment.
- Add direct `CopernicusERA5LandProvider` access for independent validation and citation.

## Phase 2: model validation

- Compare the PV model with a maintained, validated solar library.
- Add hub-height wind-speed conversion only with site roughness and measurement metadata.
- Validate battery behavior against selected equipment specifications.
- Add grid import/export limits, tariffs, and time-varying carbon intensity.
- Track stored-energy provenance for defensible renewable-fraction reporting.
- Add regression fixtures from source-attributed field or benchmark data.

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
