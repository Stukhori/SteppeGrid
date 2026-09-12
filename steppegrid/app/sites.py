"""Production views for the seven SteppeGrid settlements."""
from __future__ import annotations
from html import escape
import pandas as pd
import streamlit as st
import altair as alt
import pydeck as pdk
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

def _map_rows(registry: SiteRegistry) -> list[dict]:
    rows = []
    for site in site_rows(registry):
        featured = site["site_id"] == FEATURED_SITE_ID
        rows.append({
            "site_id": site["site_id"],
            "name": site["Site"],
            "region": site["Region"],
            "latitude": site["lat"],
            "longitude": site["lon"],
            "annual_demand": f'{site["Annual demand (GWh/year)"]:,.2f} GWh/year',
            "weather": site["Weather"],
            "result_95": site["95% result"],
            "result_99": site["99% result"],
            "identity": FEATURED_SITE_LABEL if featured else "SteppeGrid site",
            "color": [223, 165, 47, 235] if featured else [13, 118, 100, 220],
        })
    return rows

def render_site_map(registry: SiteRegistry, *, key: str = "site_map") -> None:
    """Render a map-led, keyboard-accessible village planning workspace."""
    rows = _map_rows(registry)
    selected_key = f"{key}_selected_site"
    selector_key = f"{key}_keyboard_choice"
    pending_key = f"{key}_pending_selection"
    options = [row["site_id"] for row in rows]
    pending_selection = st.session_state.pop(pending_key, None)
    if pending_selection in options:
        st.session_state[selected_key] = pending_selection
        st.session_state[selector_key] = pending_selection
    is_focused = selected_key in st.session_state
    selected_id = st.session_state.get(selected_key, FEATURED_SITE_ID)
    if selected_id not in options:
        selected_id = FEATURED_SITE_ID
        st.session_state.pop(selected_key, None)
        is_focused = False
    if selector_key not in st.session_state or st.session_state[selector_key] not in options:
        st.session_state[selector_key] = selected_id
    section_header("Village planning map", "Select a marker or use the village field to inspect demand, resource data, and saved results.")
    map_column, summary_column = st.columns([2.15, 1], gap="large")
    with summary_column:
        keyboard_choice = st.selectbox(
            "Village",
            options,
            format_func=lambda site_id: next(row["name"] for row in rows if row["site_id"] == site_id),
            key=selector_key,
            help="Keyboard-accessible alternative to selecting a map marker.",
        )
    if keyboard_choice != selected_id:
        selected_id = keyboard_choice
        st.session_state[selected_key] = selected_id
        is_focused = True
    selected = next(row for row in rows if row["site_id"] == selected_id)
    selected_site = registry.get_site(selected_id)
    resource = weather_summary(selected_site)
    view = pdk.ViewState(
        latitude=selected["latitude"] if is_focused else 48.0,
        longitude=selected["longitude"] if is_focused else 67.0,
        zoom=7 if is_focused else 3.15,
        pitch=0,
    )
    deck_rows = [
        {
            **row,
            "radius": 38_000 if row["site_id"] == selected_id else 28_000,
            "line_color": [11, 39, 48, 255] if row["site_id"] == selected_id else [255, 255, 255, 230],
        }
        for row in rows
    ]
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=deck_rows,
        id=f"{key}-sites",
        get_position="[longitude, latitude]",
        get_fill_color="color",
        get_radius="radius",
        radius_min_pixels=8,
        radius_max_pixels=18,
        pickable=True,
        auto_highlight=True,
        stroked=True,
        get_line_color="line_color",
        line_width_min_pixels=2,
    )
    with map_column:
        event = st.pydeck_chart(
            pdk.Deck(
                layers=[layer],
                initial_view_state=view,
                map_style=None,
                tooltip={"html": "<b>{name}</b><br>{region}<br>{identity}<br>Demand: {annual_demand}<br>Weather: {weather}<br>95% result: {result_95}<br>99% result: {result_99}"},
            ),
            on_select="rerun",
            selection_mode="single-object",
            key=key,
            height=500,
        )
        st.markdown(
            '<div class="sg-map-legend" aria-label="Map legend">'
            '<span><i class="sg-map-dot sg-map-dot--featured"></i>My Village</span>'
            '<span><i class="sg-map-dot sg-map-dot--site"></i>Registered site</span>'
            '<span class="sg-map-hint">Hover for details · select to zoom</span></div>',
            unsafe_allow_html=True,
        )
        if is_focused and st.button("Reset Kazakhstan view", key=f"{key}_reset"):
            st.session_state.pop(selected_key, None)
            st.rerun()
    objects = event.selection.get("objects", {}).get(f"{key}-sites", [])
    if objects and (objects[0]["site_id"] != selected_id or not is_focused):
        st.session_state[pending_key] = objects[0]["site_id"]
        st.rerun()
    with summary_column:
        badge = '<span class="sg-village-badge">My Village</span>' if selected_id == FEATURED_SITE_ID else '<span class="sg-village-badge sg-village-badge--site">Registered site</span>'
        st.markdown(
            f'<div class="sg-village-summary">{badge}<h3>{escape(selected["name"])}</h3>'
            f'<p>{escape(selected["region"])}</p><small>{selected["latitude"]:.4f}° N · {selected["longitude"]:.4f}° E</small></div>',
            unsafe_allow_html=True,
        )
        demand_col, wind_col = st.columns(2)
        with demand_col: metric("Annual demand", selected["annual_demand"])
        with wind_col: metric("Wind CF", percent(resource["wind_capacity_factor"], 2))
        pv_col, weather_col = st.columns(2)
        with pv_col: metric("PV yield", f'{resource["pv_specific_yield_kwh_per_kwp"]:,.0f} kWh/kWp')
        with weather_col: metric("Weather", selected["weather"])
        st.markdown(
            f'<div class="sg-result-row"><span>95% result <b>{escape(selected["result_95"])}</b></span>'
            f'<span>99% result <b>{escape(selected["result_99"])}</b></span></div>',
            unsafe_allow_html=True,
        )
        inspect_col, plan_col = st.columns(2)
        with inspect_col:
            if st.button("Inspect site", key=f"{key}_inspect", width="stretch"):
                st.session_state["_pending_inspect_site_id"] = selected_id
                st.session_state["_pending_primary_destination"] = "Sites"
                st.rerun()
        with plan_col:
            if st.button("Plan for site", type="primary", key=f"{key}_plan", width="stretch"):
                st.session_state["_pending_planner_site_id"] = selected_id
                st.session_state["_pending_primary_destination"] = "Plan a System"
                st.rerun()

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
    render_site_map(registry, key="sites_page_map")
    ids = [r["site_id"] for r in rows]
    pending_inspect = st.session_state.pop("_pending_inspect_site_id", None)
    if pending_inspect in ids:
        st.session_state["site_inspector"] = pending_inspect
    selected_id = st.selectbox("Inspect site", ids, index=ids.index(FEATURED_SITE_ID), format_func=lambda value: registry.get_site(value).name, key="site_inspector")
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
        chart=alt.Chart(frame).mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2).encode(x=alt.X("Site:N",sort=None),y=alt.Y("Value:Q",title=category),color=alt.Color("Identity:N",scale=alt.Scale(domain=["Site",FEATURED_SITE_LABEL],range=["#0F6B5C","#D89D2B"]),legend=alt.Legend(title="Identity")),tooltip=["Site","Value","Identity"]).configure_view(strokeWidth=0).configure_axis(gridColor="#E4E7E2",labelColor="#53656C",titleColor="#33474F")
        st.altair_chart(chart,width="stretch"); st.dataframe(frame,hide_index=True,width="stretch")
        section_header("Pair comparison", "Select two saved site results for a direct metric comparison.")
        left,right=st.columns(2); names=frame["Site"].tolist()
        with left: first=st.selectbox("First site",names,index=0,key="compare_first")
        with right: second=st.selectbox("Second site",names,index=min(1,len(names)-1),key="compare_second")
        pair=frame.loc[frame["Site"].isin([first,second])]
        st.dataframe(pair,hide_index=True,width="stretch")
    else: st.info("No saved cross-village results are available for this target.")
    st.caption("Normalized metrics account for village demand. Reliability is annual energy served, not uptime.")
