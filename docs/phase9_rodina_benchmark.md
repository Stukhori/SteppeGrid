# Phase 9: controlled Rodina technology benchmark

## Purpose and provenance

This benchmark applies the Phase 8 equipment models to Open-Meteo ERA5 weather at Rodina
(51.302445, 70.541645) for the 8,760 hours of the 2025 UTC+05:00 local-year carrier. It is a
controlled comparison, not equipment selection or system design.

Demand is a literature-derived hourly reconstruction, not measured hourly demand. The source
prints 7.72 GWh/year while its monthly rows sum to 8.02 GWh; this benchmark follows the
published monthly rows without correcting the discrepancy. All three load shapes preserve the
same monthly totals. Weather inputs are ERA5 temperature, 10 m and 100 m wind, GHI, DNI, and
diffuse radiation. Radiation geometry uses the midpoint of Open-Meteo's preceding-hour interval.

Raw output means one physical turbine or the stated deterministic PV array. Capacity-normalized
results divide by rated/installed capacity. Coincidence traces are analytically rescaled to the
8.02 GWh annual load solely to compare timing; this is not a deployable equipment count.

## ERA5-derived wind shear

The primary hub-height conversion uses a representative exponent derived from the paired ERA5
10 m and 100 m series. For each finite hour with both speeds at least 0.5 m/s:

`alpha = ln(v100 / v10) / ln(100 / 10)`

The fixed threshold prevents logarithmic instability and is not a calm-wind correction. Negative
shear is retained. Sixty hours were excluded by the threshold; 8,700 were valid. In the complete
series, 62 hours had 100 m speed no greater than 10 m speed. The selected estimator is the median,
**0.231761**. This is an ERA5-derived reference-year quantity, not a site measurement.

Hourly alpha had mean 0.234761, 5th/25th/75th/95th percentiles
0.102782/0.152535/0.307470/0.394590, and range -0.240332 to 0.497611. Monthly medians ranged
from 0.151997 in July to 0.253510 in February. The fixed annual median therefore deliberately
does not model seasonal shear variation.

| Shear case | Mean reconstructed 10 m m/s | Bias m/s | MAE m/s | RMSE m/s | Pearson r |
|---|---:|---:|---:|---:|---:|
| ERA5-derived median (primary) | 3.612 | +0.020 | 0.568 | 0.669 | 0.914 |
| Generic 1/7 reference | 4.432 | +0.841 | 0.911 | 1.141 | 0.914 |

Actual ERA5 mean 10 m speed was 3.592 m/s. The identical correlations are expected because each
reconstruction is a constant scaling of the same 100 m series; bias and error magnitude distinguish
the cases. The generic Phase 8 default remains 1/7 and is not changed by this benchmark.

## Wind results

| Turbine | Rated kW | Hub m | Annual kWh/unit | kWh/kW-year | Capacity factor | Zero hours | High-wind-policy hours |
|---|---:|---:|---:|---:|---:|---:|---:|
| Skystream 3.7 | 2.1 | 10.7 | 1,003.4 | 477.8 | 5.46% | 4,103 | 0 |
| SD6 | 5.2 | 9 | 2,240.4 | 430.8 | 4.92% | 2,268 | 0 |
| Bergey Excel 15 | 15.6 | 30 | 21,903.3 | 1,404.1 | 16.03% | 1,313 | 0 |

Mean ERA5 100 m wind was 6.159 m/s. With generic alpha=1/7, the same turbines produce 2,075.2,
4,984.6, and 29,772.0 kWh/year (capacity factors 11.28%, 10.94%, and 21.79%). No simulated hour
exceeded a final certified curve bin, so the documented hold-last policy was not invoked. No
turbine-specific shear fit, hub-height search, or equipment optimization was performed.

## PV results

Phase 9 fixes tilt at latitude (51.302445 degrees) and azimuth at 180 degrees clockwise from north.
Tilt is a reference heuristic and is not optimized. Module count is `floor(AC nameplate/module STC
kW)`, giving DC/AC close to but not above 1.0. This is energy-model sizing, not string engineering.

| Module / inverter | Panels | DC kWp | AC kW | Annual AC kWh | AC kWh/kWp | Conversion loss kWh | Clipping kWh |
|---|---:|---:|---:|---:|---:|---:|---:|
| Trina 450 / SMA | 111 | 49.95 | 50 | 69,531.1 | 1,392.0 | 1,564.1 | 0.48 |
| Trina 450 / Fronius | 222 | 99.90 | 100 | 139,630.4 | 1,397.7 | 2,559.4 | 1.63 |
| REC 470 / SMA | 106 | 49.82 | 50 | 69,375.7 | 1,392.5 | 1,560.6 | 0.23 |
| REC 470 / Fronius | 212 | 99.64 | 100 | 139,318.6 | 1,398.2 | 2,553.7 | 0.88 |
| Trina 460 / SMA | 108 | 49.68 | 50 | 69,155.6 | 1,392.0 | 1,555.7 | 0.21 |
| Trina 460 / Fronius | 217 | 99.82 | 100 | 139,518.7 | 1,397.7 | 2,557.4 | 1.46 |

Annual POA irradiation was 1,440.2 kWh/m2. PV results are unchanged by the wind-shear audit.

## Annual-energy-normalized coincidence

The ranges cover all turbines or valid PV/hybrid combinations. Direct fraction is reconstructed
annual load served contemporaneously without storage.

| Load reconstruction | Wind direct fraction | PV direct fraction | Fixed 50/50 hybrid direct fraction |
|---|---:|---:|---:|
| Flat within month | 44.73-54.15% | 38.87-38.93% | 58.95-63.46% |
| Residential-like | 42.88-51.73% | 35.41-35.47% | 53.68-57.64% |
| Community-facility-like | 37.53-45.51% | 59.27-59.39% | 67.30-71.22% |

The fixed hybrid assigns exactly half the 8.02 GWh analytical budget to wind and half to PV. No
mix search was performed. For the Skystream/Trina 450/SMA reference, hourly wind/PV Pearson
correlation was -0.1171. At least one resource produced in 7,173 hours; both were below 1% of
their peaks in 1,768 hours. Monthly normalized wind share ranged from 16.8% in July to 81.8% in
December.

## Fixed one-unit storage benchmark

Storage uses the analytically normalized Skystream + Trina 450/SMA 50/50 hybrid. Each case starts
at product minimum SOC, giving zero initial dischargeable inventory. Dispatch is direct renewable
to load, surplus charging, curtailment, then battery discharge. These are not equal-capacity rankings.

| Load shape | Battery | Baseline unmet MWh | With-storage unmet MWh | Improvement MWh | Served fraction | Equivalent full cycles |
|---|---|---:|---:|---:|---:|---:|
| Flat | Tesla Megapack | 3,257.4 | 2,358.8 | 898.6 | 70.59% | 233.2 |
| Flat | Saft Intensium | 3,257.4 | 2,702.2 | 555.2 | 66.31% | 254.1 |
| Residential | Tesla Megapack | 3,696.1 | 2,620.4 | 1,075.7 | 67.33% | 279.1 |
| Residential | Saft Intensium | 3,696.1 | 3,033.3 | 662.7 | 62.18% | 303.3 |
| Community facility | Tesla Megapack | 2,617.7 | 1,985.2 | 632.5 | 75.25% | 164.1 |
| Community facility | Saft Intensium | 2,617.7 | 2,154.2 | 463.5 | 73.14% | 212.1 |

Initial-inventory discharge was zero to floating-point tolerance in every case. Generation-side,
load-side, and storage energy balances also closed to floating-point tolerance.

## Limitations and Phase 10 boundary

Wind uses a fixed annual median ERA5-derived shear exponent, not measured site shear or a
time-varying shear model. It omits density correction, wakes, icing, turbulence, and availability,
and uses an explicit hold-last assumption outside certified curves. Generic alpha=1/7 is retained
only as a reference sensitivity. PV uses fixed orientation, a simplified NOCT temperature model,
constant inverter efficiency, and no shading, snow, or soiling loss. Batteries omit degradation,
thermal constraints, and lifetime effects.

No price data, equipment ranking, turbine/panel/battery count search, orientation search, DC/AC
optimization, wind/PV ratio search, reliability optimization, LCOE, or Phase 10 sizing was performed.
