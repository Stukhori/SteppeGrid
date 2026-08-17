# SteppeGrid in Plain Language

Many villages have strong wind or sunshine, but that does not automatically mean a renewable electricity system will work every hour. A village may need the most electricity at night, during winter, or during a calm period. Batteries can move energy from one hour to another, but they add cost and have limits. SteppeGrid was built to make these tradeoffs visible.

The platform starts with a village location, one year of hourly weather, and an electricity-demand profile. It estimates how much electricity selected wind turbines and solar panels could generate each hour. It then follows a battery’s state of charge: renewable electricity serves the village first, extra energy can charge the battery, and the battery can help when generation is low. Any remaining shortage is counted as unmet electricity, while unused surplus is counted as curtailment.

SteppeGrid can search combinations of real equipment sizes and recommend a system for supplying at least 95% or 99% of modeled annual electricity demand. It reports the wind, solar, and battery capacities; how much electricity is served; the number and duration of deficit hours; and planning costs such as upfront cost and lifetime net present cost. A 99% target means 99% of annual energy is served—it does not mean 99% uptime.

The finished application includes seven Kazakhstan settlements: Rodina, Shamshi Kaldayakova, Katon-Karagay, Kegen, Shayan, Sai-Otes, and Togyzkuduk. Users can explore them on a map, review demand and renewable resources, compare saved results using size-normalized metrics, and run their own planning scenario.

Shamshi Kaldayakova is highlighted in blue as `MY VILLAGE`. Its current registered demand is 0.50 GWh per year. The latest saved 95% planning result uses 348.4 kW of wind, 299.7 kWdc of solar, and 7.71 MWh of storage, supplying 95.66% of modeled annual electricity. The current figures are active planning data, not a claim of on-site metering. The software keeps its source records and data hashes so future field measurements can be substituted cleanly.

SteppeGrid is designed for transparent exploration rather than a construction quote. It helps students, researchers, communities, and decision-makers understand why renewable system design depends on hourly timing—not only annual totals.
