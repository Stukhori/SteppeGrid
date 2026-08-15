# Data Sources

## Current Data Sources

### Open-Meteo ERA5 historical reanalysis

- Provider: [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)
- Endpoint: `https://archive-api.open-meteo.com/v1/archive`
- Selected model: ERA5, explicitly requested as `models=era5`
- Temporal resolution: hourly
- Dataset-level spatial resolution: 0.25 degrees, approximately 25 km
- Variables: `temperature_2m`, `wind_speed_10m`, `shortwave_radiation`
- Requested units: celsius, m/s, W/m2
- Timezone: UTC

ERA5 combines a numerical model with assimilated observations to reconstruct historical weather. It is not a station observation at the requested coordinate. Gridded reanalysis cannot resolve every local terrain, surface, obstacle, or building effect; this limitation is especially important for wind-resource assessment.

Every successful request retains the raw API response, request parameters and URL, retrieval time, selected model, returned grid coordinates, normalized CSV, and provenance metadata. Cache files are deliberately excluded from Git.

### User-supplied CSV

SteppeGrid does not download or bundle a real historical weather dataset. `CSVWeatherProvider` loads a user-supplied normalized file with this exact schema:

```text
timestamp,wind_speed_m_s,solar_irradiance_w_m2,temperature_c
2025-01-01T00:00:00+00:00,5.1,0,-12.3
```

Timestamps must be valid ISO 8601, unique, chronological, and exactly hourly. Every requested `[start, end)` timestamp must exist. Blanks, negative wind or irradiance, and irradiance above the configured ceiling are rejected. No interpolation, imputation, or silent unit conversion is performed.

Weather provenance records source, optional retrieval time, requested coordinates and period, original and normalized units, and processing notes. A researcher supplying a CSV remains responsible for recording the upstream dataset citation, license, spatial resolution, measurement height, transformations, and quality controls.

Turbine power curves use:

```text
wind_speed_m_s,power_kw
```

The scenario records optional turbine name, manufacturer, rating, source, evidence type, and notes. These fields describe the curve; they do not validate its scientific quality.

### User-supplied electricity load

`CSVLoadProvider` accepts strictly hourly total demand and optional explicit critical demand. It records a user-declared evidence classification and source type; it does not infer that a file is measured. The default is `UNSPECIFIED`. Missing records, duplicates, blanks, negative/non-finite energy, mixed UTC offsets, and critical energy above total energy are errors. See [load data](load_data.md) for schemas, evidence hierarchy, and field-data preparation.

### Rodina literature-derived benchmark

The checked-in Rodina source transcription cites [DOI 10.47533/2026.1606-146X.1-03](https://doi.org/10.47533/2026.1606-146X.1-03). Table 1 supplies monthly modelled load and generation values, not a released hourly utility dataset. Source metadata also preserves the paper's contextual sector load ranges and one-hour/8,760-hour modelling statements without using those ranges to infer hourly load.

The printed annual load, wind, and total-generation values conflict with sums of their printed monthly rows. SteppeGrid reports both, classifies reconstructed hourly profiles as `LITERATURE_DERIVED`, and records that hourly values are reconstructed rather than measured.

`data/benchmarks/rodina/site.yaml` adds a verified Rodina ERA5 sampling anchor at `51.302445, 70.541645`, described as a point within or associated with the village rather than an asserted centroid. The paired workflow retrieves Open-Meteo ERA5 weather for the exact UTC interval matching the UTC+05:00 local 2025 carrier. Cached raw weather remains under the ignored weather cache rather than becoming bundled benchmark evidence. Paired artifacts retain separate publication/load and provider/weather provenance chains.

## Synthetic Data

`SyntheticWeatherProvider`, `examples/scenarios/synthetic_household.yaml`, and `data/turbine_curves/synthetic_example.csv` exist solely for deterministic development and testing. Their coordinates, weather, demand, outage, equipment sizes, and power curve are arbitrary software fixtures. They are not representative of Kazakhstan, a household, a commercial turbine, or an actual project site.

## Planned Data Sources

A future direct `CopernicusERA5LandProvider` should support independent validation, research-grade dataset citation, and higher-resolution ERA5-Land point series where appropriate. It must use the same provider-neutral `WeatherDataset` boundary and preserve raw/source provenance.

No representative Kazakhstan load, tariff, grid-carbon, cost, or outage source has been selected. User-supplied load now has an explicit provenance boundary, but scientific suitability remains the researcher's responsibility. The other inputs require their own provenance and uncertainty treatment.

## Measured HelixGen Data

Empirical HelixGen power-curve data has not been integrated into this repository. The software makes no HelixGen performance or comparative advantage claim. Future measured data must include test conditions, instrumentation, uncertainty, source, and permission for use before it is loaded through the generic turbine interface.
