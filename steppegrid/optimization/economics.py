"""Structured 2022-real-USD reference planning economics."""

from __future__ import annotations
from pydantic import Field, model_validator
from steppegrid.simulation.models import DomainModel

class CostAssumption(DomainModel):
    technology: str; scale_category: str; applicable_scale: str
    capex_unit: str; capex_value: float | None = Field(default=None, gt=0)
    fixed_om_unit: str; fixed_om_value: float = Field(ge=0); lifetime_years: int = Field(gt=0)
    source_title: str; source_url: str; source_organization: str; source_year: int
    base_year: int; currency: str; geographic_scope: str; source_type: str
    cost_boundary: str; notes: str
    @model_validator(mode="after")
    def cost_required(self):
        if self.capex_value is None: raise ValueError("missing cost cannot be treated as zero")
        return self

class FinancialAssumptions(DomainModel):
    horizon_years: int = Field(gt=0); real_discount_rate: float = Field(ge=0, lt=1)
    currency: str; base_year: int; replacement_treatment: str; residual_value_treatment: str
    source_title: str; source_url: str; source_organization: str; geographic_scope: str; notes: str

def crf(rate, years):
    return 1 / years if rate == 0 else rate * (1 + rate) ** years / ((1 + rate) ** years - 1)

def component_cost(initial_capex, annual_om, lifetime, financial):
    replacement_years = list(range(lifetime, financial.horizon_years, lifetime))
    replacements = sum(initial_capex / (1 + financial.real_discount_rate) ** year for year in replacement_years)
    om = annual_om * (financial.horizon_years if financial.real_discount_rate == 0 else
        (1 - (1 + financial.real_discount_rate) ** -financial.horizon_years) / financial.real_discount_rate)
    npc = initial_capex + replacements + om
    return {"initial_capex_usd": initial_capex, "replacement_pv_usd": replacements,
        "om_pv_usd": om, "net_present_cost_usd": npc,
        "equivalent_annual_cost_usd": npc * crf(financial.real_discount_rate, financial.horizon_years),
        "replacement_years": replacement_years}

FINANCIAL = FinancialAssumptions(horizon_years=25, real_discount_rate=.03, currency="USD",
    base_year=2022, replacement_treatment="like-for-like at constant real cost",
    residual_value_treatment="zero residual value",
    source_title="2024 Annual Supplement to NIST Handbook 135",
    source_url="https://www.energy.gov/cmei/femp/articles/annual-supplement-nist-handbook-135",
    source_organization="U.S. DOE Federal Energy Management Program",
    geographic_scope="U.S. federal lifecycle-cost reference",
    notes="The 3% real rate is a reference planning assumption, not Rodina investor financing. Horizon, replacements, and zero salvage are explicit Phase 10 benchmark choices.")
WIND = CostAssumption(technology="distributed wind, 20-kW class", scale_category="distributed_wind_reference",
    applicable_scale="extrapolated per-kW reference for fleets of catalog small turbines",
    capex_unit="USD/kW", capex_value=8425,
    fixed_om_unit="USD/kW-year", fixed_om_value=39, lifetime_years=25,
    source_title="2022 Cost of Wind Energy", source_url="https://www.nrel.gov/docs/fy24osti/88335.pdf",
    source_organization="NREL", source_year=2022, base_year=2022, currency="USD",
    geographic_scope="United States technology-class reference", source_type="national laboratory",
    cost_boundary="installed CAPEX including turbine and balance of system",
    notes="Not manufacturer pricing or a Kazakhstan contractor quotation.")
PV = CostAssumption(technology="commercial PV", scale_category="commercial_pv",
    applicable_scale="PV systems with installed AC nameplate at or below 5 MWac",
    capex_unit="USD/kWdc", capex_value=1990,
    fixed_om_unit="USD/kWdc-year", fixed_om_value=21, lifetime_years=25,
    source_title="2024 Annual Technology Baseline: Commercial PV",
    source_url="https://atb.nrel.gov/electricity/2024/commercial_pv", source_organization="NREL",
    source_year=2022, base_year=2022, currency="USD", geographic_scope="United States reference",
    source_type="national laboratory", cost_boundary="installed commercial PV including inverter and BOS",
    notes="Not Kazakhstan-specific; source reports $1.99/Wdc and about $21/kWdc-year.")
BATTERY = CostAssumption(technology="lithium-ion storage, four-hour reference", capex_unit="USD/kWh",
    scale_category="generic_lithium_ion_storage_reference",
    applicable_scale="common technology-class valuation for both catalog battery products",
    capex_value=482, fixed_om_unit="fraction of CAPEX/year", fixed_om_value=.025, lifetime_years=15,
    source_title="Cost Projections for Utility-Scale Battery Storage: 2023 Update",
    source_url="https://www.nrel.gov/docs/fy23osti/85332.pdf", source_organization="NREL",
    source_year=2022, base_year=2022, currency="USD", geographic_scope="United States reference",
    source_type="national laboratory", cost_boundary="installed four-hour lithium-ion system",
    notes="Technology-class proxy applied to both products; not product pricing. FOM fraction follows 2024 ATB.")

PV_UTILITY_SCALE_THRESHOLD_KW_AC = 5_000.0

UTILITY_PV = CostAssumption(technology="utility-scale PV", scale_category="utility_scale_pv",
    applicable_scale="PV systems with installed AC nameplate above 5 MWac",
    capex_unit="USD/kWac", capex_value=1430, fixed_om_unit="USD/kWac-year",
    fixed_om_value=24, lifetime_years=25,
    source_title="2024 Annual Technology Baseline: Utility-Scale PV",
    source_url="https://atb.nrel.gov/electricity/2024/utility-scale_pv",
    source_organization="NREL", source_year=2022, base_year=2022, currency="USD",
    geographic_scope="United States reference", source_type="national laboratory",
    cost_boundary="installed utility-scale PV including grid connection; AC capacity basis",
    notes="2022 market-average reference. The 5 MWac boundary follows the source page's discussion of EIA utility-scale installations greater than 5 MWac; it is not a Kazakhstan procurement threshold.")

def classify_pv_economic_scale(installed_ac_kw: float) -> str:
    if installed_ac_kw < 0: raise ValueError("installed_ac_kw must be nonnegative")
    return (PV.scale_category if installed_ac_kw <= PV_UTILITY_SCALE_THRESHOLD_KW_AC
            else UTILITY_PV.scale_category)

def pv_cost_assumption(installed_ac_kw: float) -> CostAssumption:
    return PV if classify_pv_economic_scale(installed_ac_kw) == PV.scale_category else UTILITY_PV

def system_cost(*, wind_kw: float, pv_dc_kw: float, pv_ac_kw: float,
                battery_usable_kwh: float, wind_capex_multiplier: float = 1.0,
                pv_capex_multiplier: float = 1.0,
                battery_capex_multiplier: float = 1.0) -> dict:
    if min(wind_kw, pv_dc_kw, pv_ac_kw, battery_usable_kwh) < 0:
        raise ValueError("installed capacities must be nonnegative")
    if min(wind_capex_multiplier, pv_capex_multiplier, battery_capex_multiplier) < 0:
        raise ValueError("CAPEX multipliers must be nonnegative")
    parts = {}; classes = {}; bases = {}
    if wind_kw:
        parts["wind"] = component_cost(wind_kw * WIND.capex_value * wind_capex_multiplier,
            wind_kw * WIND.fixed_om_value, WIND.lifetime_years, FINANCIAL)
        classes["wind"] = WIND.scale_category; bases["wind"] = f"{WIND.capex_value} {WIND.capex_unit}"
    if pv_dc_kw or pv_ac_kw:
        assumption = pv_cost_assumption(pv_ac_kw)
        capacity = pv_dc_kw if assumption.capex_unit == "USD/kWdc" else pv_ac_kw
        parts["pv"] = component_cost(capacity * assumption.capex_value * pv_capex_multiplier,
            capacity * assumption.fixed_om_value, assumption.lifetime_years, FINANCIAL)
        classes["pv"] = assumption.scale_category; bases["pv"] = f"{assumption.capex_value} {assumption.capex_unit}"
    if battery_usable_kwh:
        capex = battery_usable_kwh * BATTERY.capex_value * battery_capex_multiplier
        parts["battery"] = component_cost(capex, capex * BATTERY.fixed_om_value,
            BATTERY.lifetime_years, FINANCIAL)
        classes["battery"] = BATTERY.scale_category
        bases["battery"] = f"{BATTERY.capex_value} {BATTERY.capex_unit}"
    return {"initial_capex_usd": sum(v["initial_capex_usd"] for v in parts.values()),
        "net_present_cost_usd": sum(v["net_present_cost_usd"] for v in parts.values()),
        "equivalent_annual_cost_usd": sum(v["equivalent_annual_cost_usd"] for v in parts.values()),
        "economic_classes": classes, "reference_capex_basis": bases,
        "economic_sources": {"wind": WIND.source_url if wind_kw else None,
            "pv": pv_cost_assumption(pv_ac_kw).source_url if pv_dc_kw or pv_ac_kw else None,
            "battery": BATTERY.source_url if battery_usable_kwh else None}}
