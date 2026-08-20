"""Production views for the seven SteppeGrid settlements."""
from __future__ import annotations
import pandas as pd
import streamlit as st
import altair as alt
from steppegrid.app.components import metric, page_header, section_header
from steppegrid.app.product import FEATURED_SITE_ID, FEATURED_SITE_LABEL, latest_result, site_rows, weather_summary
from steppegrid.app.formatting import energy, money, percent, power
from steppegrid.sites import SiteRegistry

def _demand(site):
    return site.demand_datasets[0].annual_energy_kwh if site.demand_datasets else None

def _site_rows(registry: SiteRegistry):
    """Legacy internal audit projection; intentionally not rendered in public views."""
    rows=[]
    for site in registry.list_sites():
        demand=site.demand_datasets[0] if site.demand_datasets else None
        rows.append({"Site":site.name,"Site ID":site.site_id,"Region":site.region,"Classification":site.classification.value,"Population":f"~{site.population:,}" if site.population and site.population_is_approximate else (f"{site.population:,}" if site.population else "Not registered"),"Weather":registry.get_weather_status(site.site_id).value,"Planning":registry.get_planning_readiness(site.site_id).value,"Demand evidence":"Proxy-derived demand" if demand and demand.classification.value=="PROXY_DERIVED" else "Registered demand"})
    return rows

def render_sites(registry: SiteRegistry) -> None:
    page_header("Explore Kazakhstan", "Sites", "Seven rural settlements with registered demand and cached hourly weather.", [("7 VILLAGES", "success"), ("8,760 HOURS", "info")])
    browse_tab, add_tab = st.tabs(["Browse sites", "Add new site"])
    with add_tab:
        st.write("Registering a new local planning site remains available for private analysis; production views always contain the seven configured villages.")
        st.text_input("Site ID", key="onboard_site_id")
        st.button("Validate and save site", disabled=True, help="Complete site registration through the typed registry workflow.")
    rows = site_rows(registry)
    section_header("Village overview", "Planning values and saved-result availability at a glance.")
    st.dataframe(pd.DataFrame(rows).drop(columns=["site_id", "lat", "lon", "featured_site"]), hide_index=True, width="stretch")
    section_header("Kazakhstan map", "The blue identity marks My Village; it is not a performance rating.")
    st.map(pd.DataFrame(rows), latitude="lat", longitude="lon", color="#2878D8", size=24)
    st.caption("🔵 MY VILLAGE — Shamshi Kaldayakova · Other markers — SteppeGrid sites")
    ids = [r["site_id"] for r in rows]
    selected_id = st.selectbox("Inspect site", ids, index=ids.index(FEATURED_SITE_ID), format_func=lambda value: registry.get_site(value).name)
    site = registry.get_site(selected_id)
    st.download_button("Export site JSON", registry.export_site(selected_id), file_name=f"{selected_id}.site.json", mime="application/json")
    css = " sg-featured-site" if selected_id == FEATURED_SITE_ID else ""
    badge = f'<span class="sg-featured-badge">{FEATURED_SITE_LABEL}</span>' if selected_id == FEATURED_SITE_ID else ""
    st.markdown(f'<div class="sg-site-detail{css}">{badge}<h2>{site.name}</h2><p>{site.region} · {site.latitude:.4f}, {site.longitude:.4f}</p></div>', unsafe_allow_html=True)
    section_header("Location & electricity")
    a,b,c,d = st.columns(4)
    with a: metric("Annual demand", energy(_demand(site)) if _demand(site) else "Not available")
    with b: metric("Population", f"{site.population:,}" if site.population else "Not available")
    with c: metric("Weather", "Cached · 2025")
    with d: metric("Hourly coverage", "8,760 hours")
    resource = weather_summary(site)
    section_header("Renewable resource")
    a,b = st.columns(2)
    with a: metric("Modeled wind capacity factor", percent(resource.get("wind_capacity_factor", float("nan")), 2))
    with b: metric("Modeled PV yield", f"{resource.get('pv_specific_yield_kwh_per_kwp', float('nan')):,.0f} kWh/kWp")
    section_header("Selected systems", "Saved planning results are shown directly; unavailable targets are not inferred.")
    for column,target in zip(st.columns(2),(.95,.99),strict=True):
        with column:
            result = latest_result(selected_id,target)
            if selected_id == "rodina": st.info(f"{target:.0%} Rodina Benchmark available on System Design.")
            elif not result: st.info(f"{target:.0%} planning result not available.")
            else:
                design,perf,econ=result["design"],result["metrics"],result["economics"]
                st.markdown(f"### {target:.0%} system")
                st.write(f"Wind {power(design['wind_capacity_kw'])} · Solar {power(design['pv_ac_capacity_kw'])} AC · Storage {energy(design['battery_usable_capacity_kwh'])}")
                st.write(f"{percent(perf['served_fraction'],2)} annual energy served · {perf['loss_of_load_hours']:,} LOLH · {money(econ['net_present_cost_usd'])} NPC")

def render_compare_sites(registry: SiteRegistry) -> None:
    page_header("Cross-village planning", "Compare Sites", "Compare saved systems using size-aware metrics. Blue identifies My Village, not the best performer.", [("95% / 99%", "info"), ("MY VILLAGE", "featured")])
    target=st.segmented_control("Annual energy served target",["95%","99%"],default="95%")
    category=st.segmented_control("Metric",["System Cost","Wind","Solar","Storage","Reliability","Curtailment"],default="System Cost")
    rows=[]
    for site in registry.list_sites():
        result=latest_result(site.site_id,.95 if target=="95%" else .99)
        if not result: continue
        demand=_demand(site) or result.get("annual_demand_kwh"); design,perf,econ=result["design"],result["metrics"],result["economics"]
        values={"System Cost":econ.get("net_present_cost_usd",0)/demand,"Wind":design.get("wind_capacity_kw",0)/(demand/1000),"Solar":design.get("pv_ac_capacity_kw",0)/(demand/1000),"Storage":design.get("battery_usable_capacity_kwh",0)/(demand/1000),"Reliability":100*perf.get("served_fraction",0),"Curtailment":100*perf.get("curtailment_fraction",0)}
        rows.append({"Site":site.name,"Value":values[category],"Identity":FEATURED_SITE_LABEL if site.site_id==FEATURED_SITE_ID else "Site"})
    if rows:
        frame=pd.DataFrame(rows)
        chart=alt.Chart(frame).mark_bar().encode(x=alt.X("Site:N",sort=None),y=alt.Y("Value:Q",title=category),color=alt.Color("Identity:N",scale=alt.Scale(domain=["Site",FEATURED_SITE_LABEL],range=["#1F6B5B","#2878D8"]),legend=alt.Legend(title="Identity")),tooltip=["Site","Value","Identity"])
        st.altair_chart(chart,width="stretch"); st.dataframe(frame,hide_index=True,width="stretch")
        section_header("Pair comparison", "Select two saved site results for a direct metric comparison.")
        left,right=st.columns(2); names=frame["Site"].tolist()
        with left: first=st.selectbox("First site",names,index=0,key="compare_first")
        with right: second=st.selectbox("Second site",names,index=min(1,len(names)-1),key="compare_second")
        pair=frame.loc[frame["Site"].isin([first,second])]
        st.dataframe(pair,hide_index=True,width="stretch")
    else: st.info("No saved cross-village results are available for this target.")
    st.caption("Normalized metrics account for village demand. Reliability is annual energy served, not uptime.")
