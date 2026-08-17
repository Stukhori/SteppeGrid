# SteppeGrid site registry

Built-in site definitions live under `builtin/<site_id>/site.json`; UI-created sites live under
`user/<site_id>/site.json`. Each file is validated against the typed Phase 16 model. Generated
weather remains in `data/weather/cache/`, while planning outputs remain under `outputs/`.

Built-in definitions are version-controlled and read-only through the UI. A new user site can be
added without changing Python code by creating it through the Sites onboarding workflow or the
`SiteRegistry` service.

Versioned demand methods live under `methodologies/`. `kz_rural_proxy_v1.json` records the
national 2022 rural-household electricity and population inputs, the explicit 1.25
community-service planning multiplier, and the resulting per-capita proxy. It is a
`PROXY_DERIVED` planning method, not measured village demand.

The production built-in registry contains Rodina, Shamshi Kaldayakova, Katon-Karagay, Kegen,
Shayan, Sai-Otes, and Togyzkuduk. Site metadata remains the single source for the Sites table,
map, planner selector, weather references, and demand datasets.
