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
    "No default electricity demand is assumed. Phase 14 planning is enabled only after the "
    "user explicitly supplies an estimate, proxy, monthly series, or hourly CSV; resulting "
    "runs are estimated-demand planning scenarios, not field optima."
)
