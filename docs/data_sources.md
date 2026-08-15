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

## Synthetic Data

`SyntheticWeatherProvider`, `examples/scenarios/synthetic_household.yaml`, and `data/turbine_curves/synthetic_example.csv` exist solely for deterministic development and testing. Their coordinates, weather, demand, outage, equipment sizes, and power curve are arbitrary software fixtures. They are not representative of Kazakhstan, a household, a commercial turbine, or an actual project site.

## Planned Data Sources

A future direct `CopernicusERA5LandProvider` should support independent validation, research-grade dataset citation, and higher-resolution ERA5-Land point series where appropriate. It must use the same provider-neutral `WeatherDataset` boundary and preserve raw/source provenance.

Load, tariff, grid-carbon, cost, and outage sources have not been selected. Each requires its own provenance and uncertainty treatment.

## Measured HelixGen Data

Empirical HelixGen power-curve data has not been integrated into this repository. The software makes no HelixGen performance or comparative advantage claim. Future measured data must include test conditions, instrumentation, uncertainty, source, and permission for use before it is loaded through the generic turbine interface.
