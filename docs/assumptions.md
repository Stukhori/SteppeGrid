# Assumptions Register

Every consequential assumption should become configurable or supported by a cited source. This register describes the current implementation, not validated facts about Kazakhstan or any particular technology.

| Area | Current assumption | Status / required evidence |
|---|---|---|
| Time | Consecutive fixed one-hour intervals; power is constant within each interval | Configurable sub-hourly duration is future work |
| Timezone | CSV load requires one explicit, consistent UTC offset; combined series require identical ISO timestamp representations | Other constructors can still create naive timestamps for legacy tests |
| Load | Total and critical demand are interval energy in kWh | No representative demand values supplied or inferred |
| Load quality | User selects an evidence classification retained in provenance | `UNSPECIFIED` is the safe default for unattributed CSV or legacy inline data |
| Load scaling | One factor scales total and critical series identically | Annual targets require one complete calendar year |
| Critical fraction | A configured fraction is constant for every hour | An assumption, never classified as measured critical demand |
| Literature monthly load | Published rows are retained separately from printed annual totals | Source discrepancies are reported, never silently reconciled |
| Rodina hourly timing | Flat or declared deterministic synthetic template scaled independently by month | No public measured hourly Rodina series is available in the source |
| Rodina reference year | Calendar carrier only; 2025 gives 8,760 hours | Publication does not establish that Table 1 represents 2025 |
| Rodina timezone | Fixed UTC+05:00 local civil time with no daylight-saving transition for weather pairing | This aligns local behavior with weather but does not establish the paper's unpublished source timestamp convention |
| Rodina site anchor | `51.302445, 70.541645` is a verified point within or associated with Rodina used for ERA5 sampling | Not asserted to be the exact village centroid; ERA5 remains gridded |
| Rodina critical load | Absent | Paper does not support a defensible village-wide critical series |
| Rodina outages | Absent from paired analysis | No verified outage schedule is inferred |
| Rodina resource correlation | Pearson association between reconstructed load and raw ERA5 irradiance or 10 m wind speed | Timing diagnostic only; not generation, coverage, or performance |
| Missing data | Any missing/misaligned hour is an error | Keep; future cleaning must be explicit upstream |
| Weather CSV | Required normalized units are m/s, W/m2, and degC | Upstream conversions must be recorded in provenance |
| Historical source | Open-Meteo ERA5 is reanalysis associated with a selected grid cell | Not a local station measurement |
| ERA5 resolution | 0.25 degrees, approximately 25 km at dataset level | Local terrain/building effects are unresolved |
| Open-Meteo dates | API dates are inclusive; SteppeGrid end datetimes are exclusive | Provider validates every selected UTC hour |
| Radiation timing | `shortwave_radiation` is the mean over the preceding hour | One-hour integration permits Wh/m2 inspection totals |
| Wind height | Open-Meteo wind is 10 m above ground | No hub-height or terrain correction is applied |
| Annual weather year | Complete calendar year in the declared analysis timezone | Pilot defaults to UTC; Rodina uses UTC+05:00 and matching shifted UTC coverage |
| Wind bands | `<2`, `2-<3`, `3-<5`, `5-8`, and `>8` m/s | Descriptive only, not turbine cut-in/out classes |
| Seasonal correlation | Pearson correlation of 12 monthly mean wind values with 12 monthly irradiation totals | Association does not establish resilience |
| Irradiance validation | CSV values must be 0-2000 W/m2 by default | Configurable screening ceiling, not a physical maximum |
| Solar | Linear irradiance scaling with a configurable performance ratio and DC-capacity cap | Replace or validate with a sourced PV model |
| Solar temperature | Temperature has no effect | Model after module/inverter specifications exist |
| PV geometry/losses | Tilt, azimuth, snow, shading, degradation, and distinct inverter losses are absent | Add only with sourced/configurable models |
| Wind | Linear interpolation between supplied empirical curve points | Curves require source, measurement conditions, and license |
| Wind bounds | Output outside the supplied curve equals its nearest endpoint | Curves must explicitly encode cut-in/cut-out endpoints |
| HelixGen | No curve or comparative advantage is assumed | Add only supplied, sourceable empirical results |
| Battery | Capacity and power do not degrade; efficiencies are constant | Add sourced equipment model later |
| Battery SOC | `capacity_kwh` is maximum SOC; `minimum_soc_kwh` is inaccessible reserve | Configurable now |
| Battery provenance | Initial SOC and all battery discharge count as renewable for renewable fraction | Replace with energy-origin tracking |
| Grid | Unlimited import power when available; no export | Add limits, export, prices, and emissions later |
| Dispatch | Renewable-first total dispatch with no forecasting; critical service uses proportional or within-hour critical-first accounting | No inter-hour reservation or optimized shedding |
| Outage | Boolean availability is known for each hour | Scheduled and stochastic generation are future work |
| Costs/emissions | Not calculated | Requires sourced, dated, configurable inputs |
| Location | Coordinates identify scenario context; synthetic weather does not use them physically | Historical providers must describe spatial resolution |

The synthetic example deliberately uses arbitrary round numbers to exercise the software. They must not be cited as typical demand, weather, equipment, or outage conditions.
