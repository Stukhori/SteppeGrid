"""Small immutable UI vocabulary."""

PAGES = (
    "Overview",
    "Demand & Weather",
    "Renewable Generation",
    "System Design",
    "Reliability",
    "Economics",
    "Sensitivity",
    "Methodology & Provenance",
)

NAVIGATION = {
    "Study": ("Overview", "Demand & Weather", "Renewable Generation"),
    "Planning": ("System Design", "Reliability", "Economics"),
    "Analysis": ("Sensitivity",),
    "Research": ("Methodology & Provenance",),
}

TARGET_LABELS = {"95% annual served-energy target": 0.95, "99% annual served-energy target": 0.99}
PROFILE_LABELS = {
    "Residential-like": "residential_like",
    "Flat within month": "flat_within_month",
    "Community-facility-like": "community_facility_like",
}

SHAMSHI_STATUS = (
    "Shamshi Kaldayakova, Aktobe Region, Kazakhstan — cached ERA5 weather is available. "
    "No default electricity demand is assumed. The registry contains a clearly labeled synthetic 500 MWh "
    "demonstration, not a default real demand. "
    "The scale-aware planner runs only after the user explicitly selects that dataset or supplies another "
    "estimate, proxy, monthly series, or hourly CSV; resulting "
    "runs are estimated-demand planning scenarios, not field optima."
)
