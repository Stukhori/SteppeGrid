# Phase 16: multi-village site registry and onboarding

## 1. Motivation and scientific boundary

Phase 16 turns site addition into a file-backed metadata, weather, demand, and provenance workflow. It does not change renewable-generation equations, battery dispatch, reliability calculations, Planner V2 search, or economics. Rodina Phase 9–12 and the Phase 15 catalog remain frozen. The registry does not perform cross-village optimization or ranking.

## 2. Typed site model

`VillageSite` records a stable filesystem-safe `site_id`, name, settlement type, country, region, optional district/demographics, coordinates, IANA timezone, fixed planning offset, classification, origin, weather references, demand-dataset references, and field-level provenance. `WeatherDatasetRef`, `DemandDatasetRef`, `SourceReference`, and `SiteRegistryAudit` are separately validated models rather than free-form site dictionaries.

Classifications are `BENCHMARK`, `FIELD_CASE`, `PLANNING_SITE`, and `CUSTOM_SITE`. Origins are `BUILT_IN` and `USER_REGISTERED`. These labels are descriptive and never alter physical equations.

Planning readiness is derived:

- invalid metadata/reference/hash → `INVALID`;
- no valid cached weather → `WEATHER_MISSING`;
- no demand dataset → `DEMAND_MISSING`;
- valid weather and demand → `READY_FOR_PLANNING`;
- the same state for a benchmark → `BENCHMARK_READY`.

Synthetic or user-provided demand generates a provenance warning but does not by itself block a numerically valid planning run.

## 3. Registry and directory structure

```text
data/sites/
  builtin/
    katon_karagay/site.json
    kegen/site.json
    rodina/site.json
    sai_otes/site.json
    shamshi_kaldayakova/site.json
    shayan/site.json
    togyzkuduk/site.json
  methodologies/
    kz_rural_proxy_v1.json
  user/
    <site_id>/
      site.json
      demand/<demand_id>.csv       # only when an hourly upload is stored

data/weather/cache/                # existing Open-Meteo/ERA5 cache
outputs/sites/<site_id>/scenarios/<scenario_id>/
outputs/site_registry/site_audit.json
```

Built-in definitions are version-controlled and read-only through `SiteRegistry`. User definitions use atomic temporary-file replacement. Removing a user site does not delete its historical scenario outputs.

## 4. Built-in migration

Rodina is registered at 51.302445, 70.541645, Akmola Region, `Asia/Almaty`, classification `BENCHMARK`. Its registry references the existing frozen 2025 local-year ERA5 cache and `rodina_phase9_reconstruction_v1`: the 8.02 GWh literature monthly-row reconstruction with its frozen hourly hash. No benchmark output is regenerated or overwritten.

Shamshi Kaldayakova is registered at 50.578333, 57.544722, Aktobe Region, `Asia/Aqtobe`, classification `FIELD_CASE`. It references the existing cached 2025 ERA5 data. `shamshi_demo_500mwh_community` is explicitly `SYNTHETIC_ESTIMATE`; it is an available demonstration dataset, not default real village demand and not field validation.

Katon-Karagay, Kegen, Shayan, Sai-Otes, and Togyzkuduk are ordinary `PLANNING_SITE` entries. Each has population and coordinate provenance, one `PROXY_DERIVED` demand dataset, and validated 2025 ERA5 weather. They are real settlements, not test or demonstration villages.

The built-in audit reports seven registered, valid, and planning-ready sites, zero blockers, and one warning for Shamshi's synthetic dataset.

## 5. Weather onboarding and invalidation

`SiteRegistry.prepare_weather()` delegates to the existing `OpenMeteoHistoricalWeatherProvider`. The provider validates hourly frequency, completeness, uniqueness, finiteness, required variables, units, returned coordinates, and UTC behavior. Existing complete caches are reused unless refresh is explicit. The registry records the provider/model/year, requested coordinates, period, variables, cache key, normalized path, metadata path, and SHA-256.

One Kegen ERA5 record contained a −7 W/m² diffuse-radiation artifact. The shared provider now applies a narrow, explicit quality-control floor only to direct/diffuse ERA5 radiation in the interval [−10, 0) W/m², records the variable and correction count in provenance, and continues to reject larger negative values. No timestamps are interpolated or imputed, and frozen Rodina/Shamshi caches are unchanged.

Changing user-site coordinates marks all attached weather references `STALE`. Planning readiness is withdrawn until weather is prepared for the new coordinates. Large gaps are never silently filled.

## 6. Demand datasets

A site owns zero or more stable `demand_id` records. Annual estimates, 12 monthly totals, strict hourly CSV uploads, and registered Rodina reconstruction are supported through the existing Phase 14 demand constructors and classifications:

`MEASURED`, `SOURCE_REPORTED`, `SOURCE_RECONSTRUCTED`, `PROXY_DERIVED`, `SYNTHETIC_ESTIMATE`, and `USER_PROVIDED`.

Each dataset records its classification, qualitative confidence label, annual energy, profile method/shape, source metadata, optional source file/hash, and deterministic hourly `demand_sha256`. Adding a newer estimate creates another ID; it never overwrites an older dataset.

### KZ_RURAL_PROXY_V1

The five added planning sites use a machine-readable method rather than a hidden application constant:

```text
2022 rural-household electricity = 4,827.4 GWh/year
2022 rural population            = 7,533,000 people
household proxy                   = 640.833665 kWh/person/year
community-service multiplier     = 1.25 (SteppeGrid planning assumption)
planning proxy                    = 801.042082 kWh/person/year
```

Annual energy is the site's documented population basis multiplied by the planning proxy and is distributed with `community_facility_like`. The multiplier is not a measured national or village statistic. Internal calculations preserve the derived float; the UI rounds population and demand to avoid false precision.

## 7. Planner reproducibility

Registered runs resolve `site_id + demand_id` into an immutable `PlanningSite` snapshot. Scenario hashes include the site snapshot/hash, demand ID/hash, catalog version, and economics version. Result and provenance files repeat:

- `site_id` and `site_metadata_hash`;
- typed site snapshot;
- `demand_id` and hourly demand hash;
- weather cache key/hash;
- `PLANNER_V2` catalog and scale-aware economics versions.

Later registry edits therefore do not mutate historical result meaning. Registered outputs are grouped under `outputs/sites/<site_id>/scenarios/`; old unregistered Phase 14 paths remain readable for compatibility.

## 8. UI workflow

The application has three concise modes: **Explore**, **Sites**, and **Plan**. The Sites page dynamically lists all seven production villages with classification, approximate population and source status, rounded annual demand, demand provenance, weather, readiness, and origin. It provides a compact registry-driven map, JSON export, local history, and protected edit/delete controls. Built-ins cannot be edited or removed.

The onboarding sequence is:

```text
Site details
→ Weather (reuse/fetch ERA5 explicitly)
→ Demand (annual, monthly, hourly, or none yet)
→ Validate
→ Ready
```

The planner dynamically reads the registry, offers all registered demand datasets without declaring a newest dataset to be truth, and retains temporary custom-coordinate scenarios.

## 9. Generic-site demonstration

`python scripts/run_phase16.py` onboarded `phase16_example_village`, a clearly synthetic software fixture at an already cached coordinate. It attached a 30,000 kWh/year synthetic dataset, validated cached ERA5, and ran a deliberately reduced Planner V2 technology selection.

The run was planning-ready with zero audit blockers. It selected two 25 kWac Trina/SMA PV blocks and one 257 kWh Sungrow ST255CS-2H battery, served 97.7409% of modeled energy, and wrote its isolated result below `outputs/phase16/sites/phase16_example_village/scenarios/`. This is architecture evidence only, not a village case study.

Observed clean-run timings were approximately 0.009 s registry load, 0.689 s registry validation, less than 0.001 s demand indexing, 0.089 s onboarding excluding weather, 0.133 s cached-weather preparation, and 1.49 s end-to-end demonstration planning. Timings are machine-specific observations.

## 10. How to add another village

1. Open **Sites → Add new site**.
2. Enter the stable site ID, name, region/country, coordinates, IANA timezone, and source description.
3. Optionally prepare 2025 ERA5; an existing exact cache is reused.
4. Attach a named annual, monthly, or hourly demand dataset, or leave demand missing.
5. Review metadata/weather/demand/provenance status.
6. Select the registered site and exact demand dataset under **Plan**.

The equivalent programmatic workflow is `SiteRegistry.onboard_site()`, `prepare_weather()`, and one of the `create_*_demand_dataset()` methods. Neither route requires optimizer, physics, or app-specific branch changes.

## 11. Limitations

The registry is local file storage, not a collaborative database. Timezones are stored as IANA names while the current planner carries one explicit fixed offset per scenario. Site weather is one ERA5 year. Kegen, Shayan, and Sai-Otes population values come from public geospatial datasets without stated reference years; Katon-Karagay is an official approximate figure, and Togyzkuduk rounds a 2021 census value. Demand evidence quality remains descriptive; there is no combined numerical confidence score. Phase 16 does not add GIS siting, batch optimization, village ranking, or cross-site scientific comparison.
