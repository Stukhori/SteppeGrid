# SteppeGrid site registry

Built-in site definitions live under `builtin/<site_id>/site.json`; UI-created sites live under
`user/<site_id>/site.json`. Each file is validated against the typed Phase 16 model. Generated
weather remains in `data/weather/cache/`, while planning outputs remain under `outputs/`.

Built-in definitions are version-controlled and read-only through the UI. A new user site can be
added without changing Python code by creating it through the Sites onboarding workflow or the
`SiteRegistry` service.
