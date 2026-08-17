# Phase 8 equipment and physical-model provenance

Catalog records live in `steppegrid/equipment/catalog.py`; each source declares the exact
parameters it supports and the 2026-08-16 access date. Wind curves are transcribed from the
tabulated, sea-level-corrected ICC-SWCC certification reports rather than reconstructed.
Small negative parasitic readings below turbine startup are bounded to zero and explicitly noted.

The wind model uses `v_h = v_100 (h/100)^alpha`, with overridable `alpha`; the default 1/7 is a
generic power-law assumption, not a site measurement. No air-density correction is applied.
The default follows NREL/TP-500-27602, which describes 1/7 as commonly used for well-exposed,
low-roughness areas: https://docs.nrel.gov/docs/fy02osti/27602.pdf.
Cut-out metadata has an explicit behavior: `speed_threshold` requires a documented numeric
threshold, `continuous_operation` means a manufacturer explicitly states there is no cut-out,
and `unknown` means the reviewed authoritative material does not establish either behavior.
`None` therefore never means “no cut-out” by itself. SD Wind Energy documents SD6 “None -
Continuous Operation” in its product leaflet; Bergey documents Excel 15 “Cut-Out Wind Speed:
None” on its product page. The Southwest Windpower Skystream manual states a 3.5 m/s cut-in
and electronic stall regulation but does not explicitly establish cut-out behavior, so it remains
`unknown`. Its manufacturer cut-in also differs from the small positive 3.0 m/s SWCC curve bin;
both facts are preserved rather than silently reconciled.

All catalog turbines use the typed `hold_last_certified_value` policy above the final SWCC bin.
This is a deterministic Phase 8 model assumption: it avoids linear/aerodynamic extrapolation and
does not create purported certified points. A documented numeric cut-out takes precedence and
sets output to zero above its threshold. Continuous-operation metadata says the machine does not
conventionally cut out; it does not certify the held output value.

Open-Meteo documents its default hourly GHI, DNI, and diffuse radiation as the mean over the
preceding hour. The API timestamp is retained for weather/load alignment, while solar geometry
uses the averaging interval midpoint (`weather_timestamp - 30 minutes`). Both timestamps remain
timezone-aware; no Rodina timestamps or record counts are shifted.

PV uses pvlib solar position and isotropic sky transposition from GHI, DNI, and DHI. Module cell
temperature is the manufacturer NOCT relation `Tcell = Tamb + (NOCT-20)/800 * POA` and DC power
is `Pstc * POA/1000 * [1 + gamma_Pmax (Tcell-25)]`. AC conversion uses a constant published
weighted efficiency: SMA European efficiency (97.8%) or Fronius European efficiency at 580 V DC
(98.2%). This is not a load-dependent inverter curve. Conversion loss is separated from clipping,
and AC output is capped at nameplate power. Azimuth is degrees clockwise from north.

Battery catalog usable capacity is source-reported except Saft, where 2.3 MWh × the documented
95% DoD = 2.185 MWh is explicitly derived. Simulator accounting now separates discharge from
initial inventory and discharge from energy charged during the run; only the latter contributes to
`renewable_fraction`.

Wind curves are evaluated without site-specific air-density correction. The current model does
not account for pressure, altitude, temperature-dependent density, turbulence intensity, wakes,
icing, availability, or electrical losses outside the certified system curve.
