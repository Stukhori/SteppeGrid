# Assumptions Register

Every consequential assumption should become configurable or supported by a cited source. This register describes the current implementation, not validated facts about Kazakhstan or any particular technology.

| Area | Current assumption | Status / required evidence |
|---|---|---|
| Time | Consecutive fixed one-hour intervals; power is constant within each interval | Configurable sub-hourly duration is future work |
| Timezone | The engine accepts timezone-aware or naive datetimes but requires exact equality | Require timezone-aware inputs before real ingestion |
| Load | Input demand is interval energy in kWh | No representative demand values supplied |
| Missing data | Any missing/misaligned hour is an error | Keep; future cleaning must be explicit upstream |
| Solar | Linear irradiance scaling with a configurable performance ratio and DC-capacity cap | Replace or validate with a sourced PV model |
| Solar temperature | Temperature has no effect | Model after module/inverter specifications exist |
| Wind | Linear interpolation between supplied empirical curve points | Curves require source, measurement conditions, and license |
| Wind bounds | Output outside the supplied curve equals its nearest endpoint | Curves should explicitly encode cut-in/cut-out endpoints |
| HelixGen | No curve or comparative advantage is assumed | Add only supplied, sourceable empirical results |
| Battery | Capacity and power do not degrade; efficiencies are constant | Add sourced equipment model later |
| Battery SOC | `capacity_kwh` is maximum SOC; `minimum_soc_kwh` is inaccessible reserve | Configurable now |
| Battery provenance | Initial SOC and all battery discharge count as renewable for renewable fraction | Replace with energy-origin tracking |
| Grid | Unlimited import power when available; no export | Add limits, export, prices, and emissions later |
| Dispatch | Renewable-first fixed dispatch with no forecasting | Make policy modular when alternatives exist |
| Outage | Boolean availability is known for each hour | Scheduled and stochastic generation are future work |
| Costs/emissions | Not calculated | Requires sourced, dated, configurable inputs |

The synthetic example deliberately uses arbitrary round numbers to exercise the software. They must not be cited as typical demand, weather, equipment, or outage conditions.
