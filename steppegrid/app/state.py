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

TARGET_LABELS = {"95% design": 0.95, "99% design": 0.99}
PROFILE_LABELS = {
    "Residential-like": "residential_like",
    "Flat within month": "flat_within_month",
    "Community-facility-like": "community_facility_like",
}

SHAMSHI_STATUS = (
    "Shamshi Kaldayakova, Aktobe Region, Kazakhstan — weather support available; real "
    "electricity-demand data pending; optimization unavailable. No Rodina or synthetic demand "
    "is substituted, and no Shamshi optimization has been performed."
)
