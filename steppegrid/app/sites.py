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
from steppegrid.app.i18n import loc
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
            "annual_demand": f'{site["Annual demand (GWh/year)"]:,.2f} ' + loc("ГВт·ч/год", "ГВт·сағ/жыл"),
            "weather": loc("Готово", "Дайын") if site["Weather"] == "Ready" else loc("Недоступно", "Қолжетімсіз"),
            "result_95": loc("Доступен", "Қолжетімді") if site["95% result"] == "Available" else loc("Нет", "Жоқ"),
            "result_99": loc("Доступен", "Қолжетімді") if site["99% result"] == "Available" else loc("Нет", "Жоқ"),
            "identity": loc("Моё село", "Менің ауылым") if featured else loc("Село SteppeGrid", "SteppeGrid ауылы"),
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
    section_header(loc("Карта планирования сёл", "Ауылдарды жоспарлау картасы"), loc("Выберите маркер или село, чтобы изучить спрос, ресурсы и сохранённые результаты.", "Сұранысты, ресурстарды және сақталған нәтижелерді зерттеу үшін маркерді немесе ауылды таңдаңыз."))
    map_column, summary_column = st.columns([2.15, 1], gap="large")
    with summary_column:
        keyboard_choice = st.selectbox(
            loc("Село", "Ауыл"),
            options,
            format_func=lambda site_id: next(row["name"] for row in rows if row["site_id"] == site_id),
            key=selector_key,
            help=loc("Доступная с клавиатуры альтернатива выбору маркера на карте.", "Карта маркерін таңдаудың пернетақтаға қолжетімді баламасы."),
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
                tooltip={"html": loc("<b>{{name}}</b><br>{{region}}<br>{{identity}}<br>Спрос: {{annual_demand}}<br>Погода: {{weather}}<br>Результат 95%: {{result_95}}<br>Результат 99%: {{result_99}}", "<b>{{name}}</b><br>{{region}}<br>{{identity}}<br>Сұраныс: {{annual_demand}}<br>Ауа райы: {{weather}}<br>95% нәтижесі: {{result_95}}<br>99% нәтижесі: {{result_99}}")},
            ),
            on_select="rerun",
            selection_mode="single-object",
            key=key,
            height=500,
        )
        st.markdown(
            f'<div class="sg-map-legend" aria-label="{escape(loc("Легенда карты", "Карта шартты белгілері"))}">'
            f'<span><i class="sg-map-dot sg-map-dot--featured"></i>{escape(loc("Моё село", "Менің ауылым"))}</span>'
            f'<span><i class="sg-map-dot sg-map-dot--site"></i>{escape(loc("Зарегистрированное село", "Тіркелген ауыл"))}</span>'
            f'<span class="sg-map-hint">{escape(loc("Наведите для подробностей · выберите для увеличения", "Толығырақ көру үшін меңзерді апарыңыз · үлкейту үшін таңдаңыз"))}</span></div>',
            unsafe_allow_html=True,
        )
        if is_focused and st.button(loc("Показать весь Казахстан", "Бүкіл Қазақстанды көрсету"), key=f"{key}_reset"):
            st.session_state.pop(selected_key, None)
            st.rerun()
    objects = event.selection.get("objects", {}).get(f"{key}-sites", [])
    if objects and (objects[0]["site_id"] != selected_id or not is_focused):
        st.session_state[pending_key] = objects[0]["site_id"]
        st.rerun()
    with summary_column:
        badge = f'<span class="sg-village-badge">{escape(loc("Моё село", "Менің ауылым"))}</span>' if selected_id == FEATURED_SITE_ID else f'<span class="sg-village-badge sg-village-badge--site">{escape(loc("Зарегистрированное село", "Тіркелген ауыл"))}</span>'
        st.markdown(
            f'<div class="sg-village-summary">{badge}<h3>{escape(selected["name"])}</h3>'
            f'<p>{escape(selected["region"])}</p><small>{selected["latitude"]:.4f}° N · {selected["longitude"]:.4f}° E</small></div>',
            unsafe_allow_html=True,
        )
        demand_col, wind_col = st.columns(2)
        with demand_col: metric(loc("Годовой спрос", "Жылдық сұраныс"), selected["annual_demand"])
        with wind_col: metric(loc("КИУМ ветра", "Жел ҚПК"), percent(resource["wind_capacity_factor"], 2))
        pv_col, weather_col = st.columns(2)
        with pv_col: metric(loc("Выработка ФЭ", "ФЭ өндіруі"), f'{resource["pv_specific_yield_kwh_per_kwp"]:,.0f} kWh/kWp')
        with weather_col: metric(loc("Погода", "Ауа райы"), selected["weather"])
        st.markdown(
            f'<div class="sg-result-row"><span>{escape(loc("Результат 95%", "95% нәтижесі"))} <b>{escape(selected["result_95"])}</b></span>'
            f'<span>{escape(loc("Результат 99%", "99% нәтижесі"))} <b>{escape(selected["result_99"])}</b></span></div>',
            unsafe_allow_html=True,
        )
        inspect_col, plan_col = st.columns(2)
        with inspect_col:
            if st.button(loc("Изучить село", "Ауылды зерттеу"), key=f"{key}_inspect", width="stretch"):
                st.session_state["_pending_inspect_site_id"] = selected_id
                st.session_state["_pending_primary_destination"] = "Sites"
                st.rerun()
        with plan_col:
            if st.button(loc("Спланировать систему", "Жүйені жоспарлау"), type="primary", key=f"{key}_plan", width="stretch"):
                st.session_state["_pending_planner_site_id"] = selected_id
                st.session_state["_pending_primary_destination"] = "Plan a System"
                st.rerun()

def render_sites(registry: SiteRegistry) -> None:
    page_header(loc("Исследуйте Казахстан", "Қазақстанды зерттеңіз"), loc("Сёла", "Ауылдар"), loc("Семь сельских населённых пунктов с зарегистрированным спросом и почасовой погодой.", "Тіркелген сұранысы мен сағаттық ауа райы бар жеті ауылдық елді мекен."), [(loc("7 СЁЛ", "7 АУЫЛ"), "success"), (loc("8 760 ЧАСОВ", "8 760 САҒАТ"), "info")])
    browse_tab, add_tab = st.tabs([loc("Просмотр сёл", "Ауылдарды шолу"), loc("Добавить площадку", "Алаң қосу")])
    with add_tab:
        st.write(loc("Регистрация новой площадки доступна для частного анализа; публичный интерфейс содержит семь настроенных сёл.", "Жаңа алаңды тіркеу жеке талдау үшін қолжетімді; жалпы интерфейсте жеті бапталған ауыл бар."))
        st.text_input(loc("Идентификатор площадки", "Алаң идентификаторы"), key="onboard_site_id")
        st.button(loc("Проверить и сохранить", "Тексеру және сақтау"), disabled=True, help=loc("Завершите регистрацию через типизированный рабочий процесс реестра.", "Тіркеуді типтелген тізілім жұмыс процесі арқылы аяқтаңыз."))
    rows = site_rows(registry)
    section_header(loc("Обзор сёл", "Ауылдарға шолу"), loc("Плановые значения и доступность сохранённых результатов.", "Жоспарлық мәндер және сақталған нәтижелердің қолжетімділігі."))
    table = pd.DataFrame(rows).drop(columns=["site_id", "lat", "lon", "featured_site"]).rename(columns={"Site": loc("Село", "Ауыл"), "Region": loc("Регион", "Өңір"), "Population": loc("Население", "Халық"), "Annual demand (GWh/year)": loc("Годовой спрос (ГВт·ч/год)", "Жылдық сұраныс (ГВт·сағ/жыл)"), "Weather": loc("Погода", "Ауа райы"), "95% result": loc("Результат 95%", "95% нәтижесі"), "99% result": loc("Результат 99%", "99% нәтижесі")})
    st.dataframe(table, hide_index=True, width="stretch")
    render_site_map(registry, key="sites_page_map")
    ids = [r["site_id"] for r in rows]
    pending_inspect = st.session_state.pop("_pending_inspect_site_id", None)
    if pending_inspect in ids:
        st.session_state["site_inspector"] = pending_inspect
    selected_id = st.selectbox(loc("Изучить село", "Ауылды зерттеу"), ids, index=ids.index(FEATURED_SITE_ID), format_func=lambda value: registry.get_site(value).name, key="site_inspector")
    site = registry.get_site(selected_id)
    st.download_button(loc("Экспортировать JSON площадки", "Алаң JSON-ын экспорттау"), registry.export_site(selected_id), file_name=f"{selected_id}.site.json", mime="application/json")
    css = " sg-featured-site" if selected_id == FEATURED_SITE_ID else ""
    badge = f'<span class="sg-featured-badge">{FEATURED_SITE_LABEL}</span>' if selected_id == FEATURED_SITE_ID else ""
    st.markdown(f'<div class="sg-site-detail{css}">{badge}<h2>{site.name}</h2><p>{site.region} · {site.latitude:.4f}, {site.longitude:.4f}</p></div>', unsafe_allow_html=True)
    section_header(loc("Расположение и электроэнергия", "Орналасуы және электр энергиясы"))
    a,b,c,d = st.columns(4)
    with a: metric(loc("Годовой спрос", "Жылдық сұраныс"), energy(_demand(site)) if _demand(site) else loc("Недоступно", "Қолжетімсіз"))
    with b: metric(loc("Население", "Халық"), f"{site.population:,}" if site.population else loc("Недоступно", "Қолжетімсіз"))
    with c: metric(loc("Погода", "Ауа райы"), loc("В кэше · 2025", "Кэште · 2025"))
    with d: metric(loc("Почасовое покрытие", "Сағаттық қамту"), loc("8 760 часов", "8 760 сағат"))
    resource = weather_summary(site)
    section_header(loc("Возобновляемые ресурсы", "Жаңартылатын ресурстар"))
    a,b = st.columns(2)
    with a: metric(loc("Моделируемый КИУМ ветра", "Модельденген жел ҚПК"), percent(resource.get("wind_capacity_factor", float("nan")), 2))
    with b: metric(loc("Моделируемая выработка ФЭ", "Модельденген ФЭ өндіруі"), f"{resource.get('pv_specific_yield_kwh_per_kwp', float('nan')):,.0f} kWh/kWp")
    section_header(loc("Выбранные системы", "Таңдалған жүйелер"), loc("Сохранённые результаты показаны напрямую; недоступные цели не выводятся.", "Сақталған нәтижелер тікелей көрсетіледі; қолжетімсіз мақсаттар шығарылмайды."))
    for column,target in zip(st.columns(2),(.95,.99),strict=True):
        with column:
            result = latest_result(selected_id,target)
            if selected_id == "rodina": st.info(loc("Эталон Родина {target:.0%} доступен в разделе конфигурации системы.", "Родина {target:.0%} эталоны жүйе конфигурациясы бөлімінде қолжетімді.", target=target))
            elif not result: st.info(loc("Результат планирования {target:.0%} недоступен.", "{target:.0%} жоспарлау нәтижесі қолжетімсіз.", target=target))
            else:
                design,perf,econ=result["design"],result["metrics"],result["economics"]
                st.markdown(loc("### Система {target:.0%}", "### {target:.0%} жүйесі", target=target))
                st.write(loc("Ветер {wind} · Солнце {solar} AC · Накопитель {storage}", "Жел {wind} · Күн {solar} AC · Жинақтау жүйесі {storage}", wind=power(design['wind_capacity_kw']), solar=power(design['pv_ac_capacity_kw']), storage=energy(design['battery_usable_capacity_kwh'])))
                st.write(loc("Обслужено {served} годовой энергии · {lolh:,} ч дефицита · ЧДД {npc}", "Жылдық энергияның {served} бөлігі өтелді · {lolh:,} тапшылық сағаты · таза дисконтталған құн {npc}", served=percent(perf['served_fraction'],2), lolh=perf['loss_of_load_hours'], npc=money(econ['net_present_cost_usd'])))

def render_compare_sites(registry: SiteRegistry) -> None:
    page_header(loc("Межсельское планирование", "Ауылдар арасындағы жоспарлау"), loc("Сравнение сёл", "Ауылдарды салыстыру"), loc("Сравните сохранённые системы по нормированным показателям. Синий цвет обозначает Моё село, а не лучший результат.", "Сақталған жүйелерді нормаланған көрсеткіштер бойынша салыстырыңыз. Көк түс үздік нәтижені емес, Менің ауылымды білдіреді."), [("95% / 99%", "info"), (loc("МОЁ СЕЛО", "МЕНІҢ АУЫЛЫМ"), "featured")])
    target=st.segmented_control(loc("Цель обслуженной годовой энергии", "Өтелген жылдық энергия мақсаты"),["95%","99%"],default="95%")
    category_labels={"System Cost":loc("Стоимость системы", "Жүйе құны"),"Wind":loc("Ветер", "Жел"),"Solar":loc("Солнце", "Күн"),"Storage":loc("Накопитель", "Жинақтау жүйесі"),"Reliability":loc("Надёжность", "Сенімділік"),"Curtailment":loc("Ограничение", "Шектеу")}
    category=st.segmented_control(loc("Показатель", "Көрсеткіш"),list(category_labels),default="System Cost",format_func=category_labels.__getitem__)
    rows=[]
    for site in registry.list_sites():
        result=latest_result(site.site_id,.95 if target=="95%" else .99)
        if not result: continue
        demand=_demand(site) or result.get("annual_demand_kwh"); design,perf,econ=result["design"],result["metrics"],result["economics"]
        values={"System Cost":econ.get("net_present_cost_usd",0)/demand,"Wind":design.get("wind_capacity_kw",0)/(demand/1000),"Solar":design.get("pv_ac_capacity_kw",0)/(demand/1000),"Storage":design.get("battery_usable_capacity_kwh",0)/(demand/1000),"Reliability":100*perf.get("served_fraction",0),"Curtailment":100*perf.get("curtailment_fraction",0)}
        rows.append({"Site":site.name,"Value":values[category],"Identity":FEATURED_SITE_LABEL if site.site_id==FEATURED_SITE_ID else "Site"})
    if rows:
        frame=pd.DataFrame(rows)
        chart=alt.Chart(frame).mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2).encode(x=alt.X("Site:N",sort=None,title=loc("Село", "Ауыл")),y=alt.Y("Value:Q",title=category_labels[category]),color=alt.Color("Identity:N",scale=alt.Scale(domain=["Site",FEATURED_SITE_LABEL],range=["#0F6B5C","#D89D2B"]),legend=alt.Legend(title=loc("Тип", "Түрі"))),tooltip=["Site","Value","Identity"]).configure_view(strokeWidth=0).configure_axis(gridColor="#E4E7E2",labelColor="#53656C",titleColor="#33474F")
        st.altair_chart(chart,width="stretch"); st.dataframe(frame.rename(columns={"Site":loc("Село", "Ауыл"),"Value":category_labels[category],"Identity":loc("Тип", "Түрі")}),hide_index=True,width="stretch")
        section_header(loc("Парное сравнение", "Жұптық салыстыру"), loc("Выберите два сохранённых результата для прямого сравнения.", "Тікелей салыстыру үшін екі сақталған нәтижені таңдаңыз."))
        left,right=st.columns(2); names=frame["Site"].tolist()
        with left: first=st.selectbox(loc("Первое село", "Бірінші ауыл"),names,index=0,key="compare_first")
        with right: second=st.selectbox(loc("Второе село", "Екінші ауыл"),names,index=min(1,len(names)-1),key="compare_second")
        pair=frame.loc[frame["Site"].isin([first,second])]
        st.dataframe(pair.rename(columns={"Site":loc("Село", "Ауыл"),"Value":category_labels[category],"Identity":loc("Тип", "Түрі")}),hide_index=True,width="stretch")
    else: st.info(loc("Для этой цели нет сохранённых межсельских результатов.", "Бұл мақсат үшін сақталған ауылдар арасындағы нәтижелер жоқ."))
    st.caption(loc("Нормированные показатели учитывают спрос села. Надёжность — доля обслуженной годовой энергии, а не время безотказной работы.", "Нормаланған көрсеткіштер ауыл сұранысын ескереді. Сенімділік — үздіксіз жұмыс уақыты емес, өтелген жылдық энергия үлесі."))
