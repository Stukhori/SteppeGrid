"""SteppeGrid v1.0 renewable microgrid planning application."""

from __future__ import annotations

from datetime import timedelta

import pandas as pd
import streamlit as st

from steppegrid.app.charts import (
    area_chart, bar_chart, date_window, line_chart, monthly_energy, preset_dates,
    sensitivity_chart, wind_comparison,
)
from steppegrid.app.components import (
    app_header, audit_status, callout, comparison_table, design_card,
    design_comparison_rows, energy_flow, equipment_card, limitations, metric,
    microgrid_schematic, overview_intro, page_header, resource_strip, section_header,
    site_status, workflow,
)
from steppegrid.app.data import AppDataError
from steppegrid.app.formatting import RECONSTRUCTION_NOTICE, SCENARIO_NOTICE, energy, money, percent, power, readable
from steppegrid.app.services import PlanningService
from steppegrid.app.planner import render_planner
from steppegrid.app.i18n import language_switch, loc, tr
from steppegrid.app.sites import render_compare_sites, render_site_map, render_sites
from steppegrid.app.product import FEATURED_SITE_ID, latest_result, phase17_findings
from steppegrid.app.state import PRIMARY_DESTINATIONS, PROFILE_LABELS, RESEARCH_PAGES, TARGET_LABELS
from steppegrid.app.theme import COLORS, apply_theme
from steppegrid.planning.service import ScenarioPlanningService
from steppegrid.sites import SiteRegistry

st.set_page_config(page_title="SteppeGrid | Rural Kazakhstan Microgrid Planning", page_icon="⚡", layout="wide", initial_sidebar_state="collapsed")
apply_theme()


@st.cache_resource
def service() -> PlanningService:
    return PlanningService()


@st.cache_resource
def scenario_service() -> ScenarioPlanningService:
    return ScenarioPlanningService()


@st.cache_resource
def site_registry() -> SiteRegistry:
    return SiteRegistry()


def target_selector(key: str) -> float:
    localized = {
        0.95: loc("95% годовой энергии", "Жылдық энергияның 95%-ы"),
        0.99: loc("99% годовой энергии", "Жылдық энергияның 99%-ы"),
    }
    label = st.segmented_control(loc("Цель надёжности", "Сенімділік мақсаты"), list(TARGET_LABELS), default=list(TARGET_LABELS)[0], key=key, format_func=lambda item: localized[TARGET_LABELS[item]])
    return TARGET_LABELS[label]


def profile_selector(key: str) -> str:
    localized = {
        "residential_like": loc("Жилой профиль", "Тұрғын үй профилі"),
        "flat_within_month": loc("Равномерно внутри месяца", "Ай ішінде біркелкі"),
        "community_facility_like": loc("Общественные объекты", "Қоғамдық нысандар"),
    }
    label = st.selectbox(loc("Восстановленный профиль нагрузки", "Қалпына келтірілген жүктеме профилі"), list(PROFILE_LABELS), key=key, format_func=lambda item: localized[PROFILE_LABELS[item]])
    return PROFILE_LABELS[label]


def rodina_overview(api: PlanningService) -> None:
    manifest = api.provenance(); site = manifest["site"]; demand = manifest["demand"]
    lower, higher = api.design(0.95), api.design(0.99)
    page_header(
        "SteppeGrid · Explore benchmark",
        "Renewable microgrid planning for rural Kazakhstan",
        f"Rodina benchmark · {site['region']} · 2025 ERA5 · {energy(demand['monthly_rows_reconstructed_annual_kwh'])} reconstructed demand",
        [("VALIDATED", "success"), ("RECONSTRUCTED DEMAND", "warning"), ("ERA5 WEATHER", "info"), ("RODINA_FROZEN_V1", "success")],
    )
    section_header("Study status", "One completed literature benchmark and one explicit-estimate planning site.")
    left, right = st.columns(2)
    with left:
        site_status("Rodina, Akmola Region", "BENCHMARK COMPLETE", ["Data: reconstructed demand + cached ERA5 weather", "Optimization: frozen 95% and 99% designs available"])
    with right:
        site_status("Shamshi Kaldayakova, Aktobe Region", "ESTIMATE WORKFLOW ENABLED", ["Weather: ERA5 support available", "Demand: user estimate, proxy, monthly totals, or hourly CSV required"], pending=True)

    section_header("The result in one view", "Annual served energy is an energy metric—not uptime.")
    for column, design, label in zip(st.columns(2), (lower, higher), ("95% DESIGN", "99% DESIGN"), strict=True):
        with column:
            equipment_card(label, f"{percent(design['worst_served_fraction'], 2)} annual demand served", money(design["net_present_cost_usd"]), {
                "Net present cost": money(design["net_present_cost_usd"]),
                "Loss-of-load": f"{design['loss_of_load_hours']} h",
                "Unmet energy": energy(design["unmet_energy_kwh"]),
            })
    npc_change = 100 * (higher["net_present_cost_usd"] / lower["net_present_cost_usd"] - 1)
    callout(
        "The Rodina reliability-cost tradeoff",
        f"Moving from 95% to 99% annual energy served increases modeled NPC by {npc_change:.1f}%—from {money(lower['net_present_cost_usd'])} to {money(higher['net_present_cost_usd'])}. This finding is specific to the frozen Rodina assumptions.",
    )
    comparison_table(design_comparison_rows(lower, higher))

    section_header("How the benchmark works")
    workflow(("Weather + demand", "Wind / PV models", "Hourly dispatch", "Reliability", "Sizing", "Economics", "Sensitivity"))
    st.caption("Normal pages use saved results. Optimization runs only when requested in Plan a System.")


def overview(api: PlanningService) -> None:
    registry = site_registry()
    hero_copy, hero_visual = st.columns([1.05, .95], gap="large", vertical_alignment="center")
    with hero_copy:
        overview_intro()
        plan_action, compare_action = st.columns(2)
        with plan_action:
            if st.button(loc("Создать сценарий для села", "Ауыл сценарийін құру"), type="primary", key="overview_plan_action", width="stretch"):
                st.session_state["_pending_primary_destination"] = "Plan a System"
                st.rerun()
        with compare_action:
            if st.button(loc("Сравнить результаты сёл", "Ауыл нәтижелерін салыстыру"), key="overview_compare_action", width="stretch"):
                st.session_state["_pending_primary_destination"] = "Compare"
                st.rerun()
    with hero_visual:
        microgrid_schematic()
    resource_strip()
    render_site_map(registry, key="overview_site_map")
    result = latest_result(FEATURED_SITE_ID, .95)
    section_header(loc("Сводка планирования", "Жоспарлау қорытындысы"), loc("Сохранённые результаты и межсельский контекст из проверенных материалов.", "Тексерілген материалдардағы сақталған нәтижелер мен ауылдар арасындағы контекст."))
    system_panel, insight_panel = st.columns([1.65, 1], gap="large")
    if result:
        design, performance, economics_data = result["design"], result["metrics"], result["economics"]
        with system_panel:
            st.markdown(f'<div class="sg-panel-kicker">{loc("Моё село · сохранённая система 95%", "Менің ауылым · сақталған 95% жүйе")}</div>', unsafe_allow_html=True)
            w,s,b,e = st.columns(4)
            with w: metric(loc("Ветер", "Жел"), power(design["wind_capacity_kw"]))
            with s: metric(loc("Солнце", "Күн"), f"{power(design['pv_dc_capacity_kw'])} DC")
            with b: metric(loc("Накопитель", "Жинақтау жүйесі"), energy(design["battery_usable_capacity_kwh"]))
            with e: metric(loc("ЧДД", "Таза дисконтталған құн"), money(economics_data["net_present_cost_usd"]))
            callout(loc("Надёжность и стоимость", "Сенімділік пен құн"), loc("Сохранённая конфигурация покрывает {served} моделируемого годового спроса. Самый длинный непрерывный дефицит — {hours} ч.", "Сақталған конфигурация модельденген жылдық сұраныстың {served} бөлігін өтейді. Ең ұзақ үздіксіз тапшылық — {hours} сағ.", served=percent(performance['served_fraction'], 2), hours=performance['longest_deficit_hours']))
    findings = phase17_findings()
    with insight_panel:
        st.markdown(f'<div class="sg-panel-kicker">{loc("Межсельский вывод", "Ауылдар арасындағы қорытынды")}</div>', unsafe_allow_html=True)
        callout(loc("Лидеры ресурсов", "Ресурс көшбасшылары"), loc("{solar} показывает наибольшую солнечную выработку, а {wind} — наибольший репрезентативный ветровой ресурс в сопоставимой группе.", "{solar} салыстырмалы топтағы ең жоғары күн өндіруін, ал {wind} ең жоғары өкілдік жел ресурсын көрсетеді.", solar=findings['highest_solar'], wind=findings['highest_wind']))
        st.markdown(f'<div class="sg-compact-stat"><span>{loc("Минимальный нормированный ЧДД при 95%", "95% кезіндегі ең төмен нормаланған таза дисконтталған құн")}</span><strong>{findings["lowest_normalized_npc"]}</strong></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="sg-compact-stat"><span>{loc("Наибольший рост ЧДД 95%→99%", "Таза дисконтталған құнның ең үлкен өсімі 95%→99%")}</span><strong>{findings["largest_escalation"]}</strong></div>', unsafe_allow_html=True)
    section_header(loc("Как работает планирование", "Жоспарлау қалай жұмыс істейді"), loc("Краткий путь от исходных данных села к сопоставимым результатам.", "Ауылдың бастапқы деректерінен салыстырмалы нәтижелерге дейінгі қысқа жол."))
    workflow((loc("Выберите село", "Ауылды таңдаңыз"), loc("Проверьте почасовые данные", "Сағаттық деректерді тексеріңіз"), loc("Определите размер системы", "Жүйе өлшемін анықтаңыз"), loc("Сравните компромиссы", "Ымыраларды салыстырыңыз")))


def demand_weather(api: PlanningService) -> None:
    page_header(loc("Исследование · Исходные данные", "Зерттеу · Бастапқы деректер"), loc("Спрос и погода", "Сұраныс пен ауа райы"), loc("Изучите факторы модели и различайте восстановленные, реанализированные и моделируемые величины.", "Модель факторларын зерттеп, қалпына келтірілген, реанализденген және модельденген шамаларды ажыратыңыз."), [("2025", "info"), (loc("8 760 ЧАСОВ", "8 760 САҒАТ"), "success"), ("UTC+05:00", "info")])
    demand_tab, weather_tab = st.tabs([loc("Восстановление спроса", "Сұранысты қалпына келтіру"), loc("Погода ERA5", "ERA5 ауа райы")])
    with demand_tab:
        profile = profile_selector("demand_profile")
        with st.spinner(loc("Подготовка согласованных рядов…", "Үйлестірілген қатарлар дайындалуда…")):
            frame = api.demand_weather_frame(profile)
        source = api.provenance()["demand"]
        section_header(loc("Опубликованные значения и выбор эталона", "Жарияланған мәндер және эталонды таңдау"))
        a, b, c = st.columns(3)
        with a: metric(loc("Опубликованное годовое значение", "Жарияланған жылдық мән"), energy(source["printed_annual_kwh"]))
        with b: metric(loc("Сумма месячных строк", "Айлық жолдар сомасы"), energy(source["monthly_rows_reconstructed_annual_kwh"]))
        with c: metric(loc("Эталон SteppeGrid", "SteppeGrid эталоны"), energy(source["monthly_rows_reconstructed_annual_kwh"]))
        callout(loc("Почему 8,02 ГВт·ч?", "Неліктен 8,02 ГВт·сағ?"), loc("В годовой строке указано 7,72 ГВт·ч, но сумма опубликованных месячных строк равна 8,02 ГВт·ч. SteppeGrid сохраняет оба значения и использует сумму месячных строк.", "Жылдық жолда 7,72 ГВт·сағ көрсетілген, ал жарияланған айлық жолдардың қосындысы 8,02 ГВт·сағ. SteppeGrid екі мәнді де сақтап, айлық жолдар қосындысын қолданады."), "warning")
        section_header(loc("Месячная энергия", "Айлық энергия"), loc("Все формы нагрузки сохраняют одинаковые опубликованные месячные итоги.", "Барлық жүктеме пішіндері бірдей жарияланған айлық қорытындыларды сақтайды."))
        st.altair_chart(bar_chart(monthly_energy(frame, "load_kwh"), "month", "energy_kwh", y_title=loc("Месячный спрос (кВт·ч)", "Айлық сұраныс (кВт·сағ)")), width="stretch")
        first, last = frame["timestamp"].iloc[0].date(), frame["timestamp"].iloc[-1].date()
        dates = st.date_input(loc("Репрезентативный почасовой интервал", "Өкілдік сағаттық аралық"), (first, min(first + timedelta(days=6), last)), min_value=first, max_value=last, key="demand_dates")
        if isinstance(dates, (tuple, list)) and len(dates) == 2:
            selected = date_window(frame, dates[0], dates[1])
            st.altair_chart(line_chart(selected, {"load_kwh": (loc("Нагрузка", "Жүктеме"), COLORS["served"])}, loc("Почасовой спрос (кВт·ч)", "Сағаттық сұраныс (кВт·сағ)")), width="stretch")
        comparison = date_window(api.demand_comparison_frame(), first, first + timedelta(days=6))
        section_header(loc("Сравнение форм нагрузки", "Жүктеме пішіндерін салыстыру"), loc("Первая неделя показывает различия по времени, но не является измеренным почасовым профилем.", "Бірінші апта уақыт бойынша айырмашылықтарды көрсетеді, бірақ өлшенген сағаттық профиль емес."))
        st.altair_chart(line_chart(comparison, {
            "flat_within_month": ("Flat within month", COLORS["neutral"]),
            "residential_like": ("Residential-like", COLORS["primary"]),
            "community_facility_like": ("Community-facility-like", COLORS["solar"]),
        }, loc("Почасовой спрос (кВт·ч)", "Сағаттық сұраныс (кВт·сағ)")), width="stretch")
        with st.expander(loc("Показать выбранные почасовые данные", "Таңдалған сағаттық деректерді көрсету")):
            st.dataframe(selected if "selected" in locals() else frame.head(168), hide_index=True, width="stretch")
        callout(loc("Происхождение данных спроса", "Сұраныс деректерінің шығу тегі"), loc("Почасовая нагрузка восстановлена из опубликованных месячных значений и не является измеренным почасовым рядом.", "Сағаттық жүктеме жарияланған айлық мәндерден қалпына келтірілген және өлшенген сағаттық қатар емес."))

    with weather_tab:
        with st.spinner(loc("Чтение зафиксированного кэша ERA5…", "Бекітілген ERA5 кэші оқылуда…")):
            weather = api.demand_weather_frame("residential_like")
        manifest = api.provenance(); site = manifest["site"]
        section_header(loc("Сводка ресурсов", "Ресурстар қорытындысы"), loc("Кэш Open-Meteo ERA5 для {lat:.6f}, {lon:.6f}; при навигации сетевые запросы не выполняются.", "{lat:.6f}, {lon:.6f} үшін Open-Meteo ERA5 кэші; навигация кезінде желілік сұраулар орындалмайды.", lat=site['latitude'], lon=site['longitude']))
        a, b, c, d = st.columns(4)
        with a: metric(loc("Средний ветер на 100 м", "100 м биіктіктегі орташа жел"), f"{weather['wind_speed_100m_m_s'].mean():.2f} m/s")
        with b: metric(loc("Годовая GHI", "Жылдық GHI"), f"{weather['ghi_w_m2'].sum()/1000:,.0f} kWh/m²")
        with c: metric(loc("Средняя температура", "Орташа температура"), f"{weather['temperature_c'].mean():.1f} °C")
        with d: metric(loc("Покрытие", "Қамту"), f"{len(weather):,} h")
        first = weather["timestamp"].iloc[0].date(); sample = date_window(weather, first, first + timedelta(days=13))
        wind_tab, solar_tab, temperature_tab = st.tabs([loc("Ветер", "Жел"), loc("Солнце", "Күн"), loc("Температура", "Температура")])
        with wind_tab:
            st.altair_chart(line_chart(sample, {"wind_speed_10m_m_s": ("10 m", COLORS["neutral"]), "wind_speed_100m_m_s": ("100 m", COLORS["wind"])}, "Wind speed (m/s)"), width="stretch")
        with solar_tab:
            st.altair_chart(area_chart(sample, {"ghi_w_m2": ("GHI", COLORS["solar"])}, "Irradiance (W/m²)"), width="stretch")
        with temperature_tab:
            st.altair_chart(line_chart(sample, {"temperature_c": ("Temperature", COLORS["curtailment"])}, "Temperature (°C)"), width="stretch")
        st.info(loc("ERA5 — сеточный реанализ, а не результаты метеоизмерений на площадке.", "ERA5 — торлық реанализ, алаңдағы метеорологиялық өлшеулер емес."))


def renewable_generation(api: PlanningService) -> None:
    page_header(loc("Возобновляемые ресурсы", "Жаңартылатын ресурстар"), loc("Возобновляемая генерация", "Жаңартылатын генерация"), loc("Сравните оборудование эталона Родина и изучите сохранённые моделируемые профили выработки.", "Родина эталонының жабдығын салыстырып, сақталған модельдік өндіру профильдерін зерттеңіз."), [(loc("ЭТАЛОН РОДИНА", "РОДИНА ЭТАЛОНЫ"), "success"), (loc("ИСТОЧНИКИ ОБОРУДОВАНИЯ", "ЖАБДЫҚ ДЕРЕККӨЗДЕРІ"), "success"), (loc("ПОГОДА ERA5", "ERA5 АУА РАЙЫ"), "info")])
    with st.spinner(loc("Загрузка сохранённых профилей оборудования…", "Сақталған жабдық профильдері жүктелуде…")):
        wind_rows, pv_rows = api.generation_catalog()
    wind, pv = pd.DataFrame(wind_rows), pd.DataFrame(pv_rows)
    section_header(loc("Ветроэнергетическое оборудование", "Жел энергетикалық жабдығы"), loc("Годовая энергия и коэффициент использования мощности показаны отдельно.", "Жылдық энергия мен қуатты пайдалану коэффициенті бөлек көрсетілген."))
    for column, row in zip(st.columns(3), wind.to_dict("records"), strict=True):
        with column:
            equipment_card(loc("ВЕТРОТУРБИНА", "ЖЕЛ ТУРБИНАСЫ"), f"{row['manufacturer']} {row['model']}", energy(row["annual_generation_kwh"]), {
                loc("Номинальная мощность", "Номиналды қуат"): power(row["rated_power_kw"]), loc("Высота ступицы", "Түпкі биіктігі"): f"{row['hub_height_m']:.1f} m", loc("КИУМ", "ҚПК"): percent(row["capacity_factor"], 2),
            })
    left, right = st.columns(2)
    with left: st.altair_chart(wind_comparison(wind, "annual_generation_kwh", "Annual energy per turbine (kWh)"), width="stretch")
    with right: st.altair_chart(wind_comparison(wind, "capacity_factor", "Capacity factor", COLORS["primary"]), width="stretch")
    selected_wind = st.selectbox(loc("Профиль турбины", "Турбина профилі"), wind["equipment_key"].tolist(), format_func=lambda key: wind.loc[wind["equipment_key"] == key, "model"].iloc[0])

    section_header(loc("Фотоэлектрические блоки", "Фотоэлектрлік блоктар"), loc("Выберите поддерживаемую пару модуля и инвертора.", "Қолдау көрсетілетін модуль мен инвертор жұбын таңдаңыз."))
    selected_pv = st.selectbox(loc("ФЭ-модуль / инвертор", "ФЭ-модуль / инвертор"), pv["equipment_key"].tolist(), format_func=lambda key: f"{pv.loc[pv['equipment_key'] == key, 'module'].iloc[0]} · {pv.loc[pv['equipment_key'] == key, 'inverter'].iloc[0]}")
    pv_row = pv.loc[pv["equipment_key"] == selected_pv].iloc[0]
    equipment_card(loc("ФЭ-БЛОК", "ФЭ-БЛОК"), f"{pv_row['module']} · {pv_row['inverter']}", energy(pv_row["annual_ac_kwh"]), {
        loc("Мощность блока", "Блок қуаты"): f"{pv_row['dc_capacity_kw']:.1f} kWdc / {pv_row['ac_capacity_kw']:.1f} kWac",
        loc("Удельная выработка", "Меншікті өндіру"): f"{pv_row['ac_specific_yield_kwh_per_kwp']:,.1f} kWh/kWp",
        loc("POA / ограничение", "POA / шектеу"): f"{pv_row['annual_poa_kwh_m2']:,.1f} kWh/m² · {pv_row['clipping_kwh']:,.1f} kWh",
    })
    trace = api.generation_frame(selected_wind, selected_pv); first = trace["timestamp"].iloc[0].date(); example = date_window(trace, first, first + timedelta(days=6))
    section_header(loc("Репрезентативные профили установок", "Қондырғылардың өкілдік профильдері"), loc("Интерактивная выработка выбранной турбины и ФЭ-блока за первую неделю.", "Таңдалған турбина мен ФЭ-блоктың бірінші аптадағы интерактивті өндіруі."))
    st.altair_chart(line_chart(example, {"wind_kwh_per_unit": ("Wind turbine", COLORS["wind"]), "pv_kwh_per_block": ("PV block", COLORS["solar"])}, "Hourly modeled energy (kWh)"), width="stretch")
    callout(loc("Границы модели", "Модель шекаралары"), loc("Кривые мощности взяты из сертификационной документации. Сдвиг ветра для Родины получен из ERA5; след турбин и схема размещения не моделируются.", "Қуат қисықтары сертификаттау құжаттарынан алынған. Родина үшін жел ығысуы ERA5-тен алынған; турбина ізі мен орналасу сұлбасы модельденбейді."))


def system_design(api: PlanningService) -> None:
    page_header(loc("Результаты планирования", "Жоспарлау нәтижелері"), loc("Конфигурация системы", "Жүйе конфигурациясы"), loc("Изучите две конфигурации эталона Родина и их почасовую диспетчеризацию.", "Родина эталонының екі конфигурациясын және олардың сағаттық диспетчерлеуін зерттеңіз."), [(loc("ЭТАЛОН РОДИНА", "РОДИНА ЭТАЛОНЫ"), "success"), (loc("СОХРАНЁННАЯ КОНФИГУРАЦИЯ", "САҚТАЛҒАН КОНФИГУРАЦИЯ"), "success")])
    target = target_selector("design_target"); design = api.design(target); summary = api.nominal_dispatch_summary(target)
    section_header(loc("Цель: {target:.0%} годовой энергии", "Мақсат: жылдық энергияның {target:.0%}", target=target), loc("Выбрана допустимая конфигурация с наименьшей стоимостью из сохранённого дискретного поиска.", "Сақталған дискретті іздеуден ең төмен құнды жарамды конфигурация таңдалды."))
    wind_col, solar_col, storage_col = st.columns(3)
    with wind_col: design_card(loc("ВЕТЕР", "ЖЕЛ"), f"{design['wind_count']} × {readable(design['wind_key'])}", power(design["installed_wind_kw"]), loc("Установленная мощность коммерческих турбин", "Коммерциялық турбиналардың орнатылған қуаты"))
    with solar_col: design_card(loc("СОЛНЦЕ", "КҮН"), loc("{count} ФЭ-блоков", "{count} ФЭ-блок", count=design['pv_count']), f"{power(design['installed_pv_ac_kw'])} AC", f"{power(design['installed_pv_dc_kw'])} DC")
    with storage_col: design_card(loc("НАКОПИТЕЛЬ", "ЖИНАҚТАУ ЖҮЙЕСІ"), f"{design['battery_count']} × {readable(design['battery_key'])}", energy(design["installed_usable_battery_kwh"]), loc("Мощность заряда/разряда: {value}", "Заряд/разряд қуаты: {value}", value=power(design['battery_power_kw'])))
    section_header(loc("Годовые показатели", "Жылдық көрсеткіштер"), loc("Итоги ограничивающего профиля из зафиксированного номинального прогона.", "Бекітілген номиналды есептегі шектеуші профиль қорытындылары."))
    a, b, c, d = st.columns(4)
    with a: metric(loc("Обслуженный годовой спрос", "Өтелген жылдық сұраныс"), percent(design["worst_served_fraction"], 3), help_key="served_energy")
    with b: metric(loc("Необеспеченная энергия", "Қамтамасыз етілмеген энергия"), energy(design["unmet_energy_kwh"]))
    with c: metric(loc("Ограничение выработки", "Өндіруді шектеу"), energy(design["curtailment_kwh"]), help_key="curtailment")
    with d: metric(loc("Ограничивающий профиль", "Шектеуші профиль"), readable(design["binding_load_profile"]), help_key="binding_profile")
    energy_flow(summary["wind_generation_kwh"], summary["pv_generation_kwh"], summary["served_energy_kwh"], summary["curtailed_energy_kwh"], summary["unmet_energy_kwh"])

    section_header(loc("95% против 99%", "95% және 99%"), loc("Повышение цели Родины требует дополнительной мощности ВИЭ и увеличивает стоимость жизненного цикла.", "Родина мақсатын көтеру қосымша жаңартылатын қуатты талап етіп, өмірлік цикл құнын арттырады."))
    lower, higher = api.design(0.95), api.design(0.99)
    comparison_table(design_comparison_rows(lower, higher))
    npc_change = 100 * (higher["net_present_cost_usd"] / lower["net_present_cost_usd"] - 1)
    callout(loc("Стоимость более высокой цели", "Жоғары мақсаттың құны"), loc("Для конфигурации 99% ЧДД выше на {change:.1f}%, а годовая необеспеченная энергия ниже на {energy} при заданных допущениях Родины.", "99% конфигурациясында таза дисконтталған құн {change:.1f}% жоғары, ал Родина үшін берілген болжамдарда жылдық қамтамасыз етілмеген энергия {energy} төмен.", change=npc_change, energy=energy(lower['unmet_energy_kwh'] - higher['unmet_energy_kwh'])))

    section_header(loc("Почасовая диспетчеризация", "Сағаттық диспетчерлеу"), loc("Выберите готовый или пользовательский интервал; все графики используют один период.", "Дайын немесе пайдаланушы аралығын таңдаңыз; барлық графиктер бір кезеңді қолданады."))
    profile = profile_selector("dispatch_profile")
    with st.spinner(loc("Почасовой расчёт выбранной конфигурации…", "Таңдалған конфигурацияның сағаттық есебі…")):
        frame = api.dispatch_frame(target, profile); events = api.deficit_events(target, profile)
    window_labels = {"First week": loc("Первая неделя", "Бірінші апта"), "Longest deficit event": loc("Самый длинный дефицит", "Ең ұзақ тапшылық"), "Highest-curtailment week": loc("Неделя максимального ограничения", "Ең көп шектеу аптасы"), "Custom": loc("Свой интервал", "Өз аралығы")}
    preset = st.segmented_control(loc("Интервал", "Аралық"), list(window_labels), default="First week", key="dispatch_preset", format_func=window_labels.__getitem__)
    first, last = frame["timestamp"].iloc[0].date(), frame["timestamp"].iloc[-1].date()
    if preset == "Custom":
        dates = st.date_input(loc("Пользовательский интервал дат", "Пайдаланушы күн аралығы"), (first, min(first + timedelta(days=6), last)), min_value=first, max_value=last, key="dispatch_dates")
        if not isinstance(dates, (tuple, list)) or len(dates) != 2:
            st.info(loc("Выберите начальную и конечную даты.", "Басталу және аяқталу күндерін таңдаңыз.")); return
        start, end = dates
    else:
        start, end = preset_dates(frame, preset, events)
        st.caption(loc("Показан период: {start:%d.%m.%Y} — {end:%d.%m.%Y}", "Көрсетілген кезең: {start:%d.%m.%Y} — {end:%d.%m.%Y}", start=start, end=end))
    window = date_window(frame, start, end)
    st.altair_chart(line_chart(window, {"load_kwh": ("Load", COLORS["text"]), "wind_generation_kwh": ("Wind", COLORS["wind"]), "pv_generation_kwh": ("PV", COLORS["solar"]), "total_generation_kwh": ("Total renewable", COLORS["served"])}, "Hourly energy (kWh)", height=320), width="stretch")
    st.altair_chart(area_chart(window, {"battery_soc_kwh": ("Battery SOC", COLORS["storage"])}, "Stored energy (kWh)"), width="stretch")
    st.altair_chart(area_chart(window, {"unmet_energy_kwh": ("Unmet", COLORS["unmet"]), "curtailment_kwh": ("Curtailment", COLORS["curtailment"])}, "Hourly energy (kWh)"), width="stretch")
    with st.expander(loc("Показать почасовые данные", "Сағаттық деректерді көрсету")):
        st.dataframe(window, hide_index=True, width="stretch")
    st.caption(loc("Количество оборудования и правила диспетчеризации зафиксированы. Этот раздел не запускает оптимизацию.", "Жабдық саны мен диспетчерлеу ережелері бекітілген. Бұл бөлім оңтайландыруды іске қоспайды."))


def reliability(api: PlanningService) -> None:
    page_header(loc("Планирование · Показатели", "Жоспарлау · Көрсеткіштер"), loc("Надёжность", "Сенімділік"), loc("Сначала разберите смысл результата, затем изучите дефициты энергии и их время.", "Алдымен нәтиженің мағынасын, содан кейін энергия тапшылығы мен оның уақытын зерттеңіз."), [(loc("ПО ЭНЕРГИИ", "ЭНЕРГИЯ БОЙЫНША"), "info"), (loc("НЕ ВРЕМЯ БЕЗОТКАЗНОЙ РАБОТЫ", "ҮЗДІКСІЗ ЖҰМЫС УАҚЫТЫ ЕМЕС"), "warning")])
    target = target_selector("reliability_target"); profile = profile_selector("reliability_profile")
    row = next(item for item in api.reliability_rows(target) if item["load_profile"] == profile)
    with st.spinner("Summarizing existing deficit timing…"):
        dispatch = api.dispatch_frame(target, profile); events = api.deficit_events(target, profile)
    callout(loc("КОНФИГУРАЦИЯ {target:.0%}", "{target:.0%} КОНФИГУРАЦИЯСЫ", target=target), loc("Обеспечено {served} годового спроса. Дефицит возникает в течение {loss} ч, самый длинный непрерывный дефицит длится {longest} ч.", "Жылдық сұраныстың {served} бөлігі өтелді. Тапшылық {loss} сағатта туындайды, ең ұзақ үздіксіз тапшылық {longest} сағатқа созылады.", served=percent(row['served_fraction'], 2), loss=row['loss_of_load_hours'], longest=row['longest_deficit_hours']))
    a, b, c = st.columns(3)
    with a: metric(loc("Обслуженный годовой спрос", "Өтелген жылдық сұраныс"), percent(row["served_fraction"], 3), help_key="served_energy")
    with b: metric(loc("Энергетический LPSP", "Энергиялық LPSP"), percent(1 - row["served_fraction"], 3), help_key="lpsp")
    with c: metric(loc("Необеспеченная энергия", "Қамтамасыз етілмеген энергия"), energy(row["unmet_energy_kwh"]))
    d, e, f = st.columns(3)
    with d: metric(loc("Часы дефицита", "Тапшылық сағаттары"), f"{row['loss_of_load_hours']} h", help_key="lolh")
    with e: metric(loc("Самый длинный дефицит", "Ең ұзақ тапшылық"), f"{row['longest_deficit_hours']} h")
    with f: metric(loc("Максимальный часовой дефицит", "Ең жоғары сағаттық тапшылық"), energy(dispatch["unmet_energy_kwh"].max()))
    section_header(loc("По восстановленным формам нагрузки", "Қалпына келтірілген жүктеме пішіндері бойынша"))
    reliability_frame = pd.DataFrame(api.reliability_rows(target)); reliability_frame["served_percent"] = reliability_frame["served_fraction"] * 100; reliability_frame["profile"] = reliability_frame["load_profile"].map(readable)
    st.altair_chart(bar_chart(reliability_frame, "profile", "served_percent", y_title="Annual demand served (%)", color=COLORS["served"]), width="stretch")
    section_header(loc("Анализ событий дефицита", "Тапшылық оқиғаларын талдау"), loc("Непрерывные периоды рассчитаны по существующему почасовому ряду; новый стандарт надёжности не применяется.", "Үздіксіз кезеңдер қолданыстағы сағаттық қатар бойынша есептелген; жаңа сенімділік стандарты қолданылмайды."))
    e1, e2, e3 = st.columns(3)
    with e1: metric("Deficit events", f"{len(events):,}")
    with e2: metric("Median duration", f"{events['duration_hours'].median():.1f} h" if not events.empty else "0 h")
    with e3: metric("Longest event", f"{events['duration_hours'].max():.0f} h" if not events.empty else "0 h")
    if not events.empty:
        durations = events["duration_hours"].value_counts().sort_index().rename_axis("duration_hours").reset_index(name="events")
        st.altair_chart(bar_chart(durations, "duration_hours", "events", x_title="Event duration (hours)", y_title="Number of events", color=COLORS["unmet"]), width="stretch")
        start, end = preset_dates(dispatch, "Longest deficit event", events); longest = date_window(dispatch, start, end)
        st.altair_chart(area_chart(longest, {"unmet_energy_kwh": ("Unmet energy", COLORS["unmet"])}, "Hourly unmet energy (kWh)"), width="stretch")
    st.info(loc("Доля обслуженной энергии показывает часть обеспеченного годового спроса, а не процент часов бесперебойного снабжения.", "Өтелген энергия үлесі үздіксіз жабдықталған сағаттардың пайызын емес, қамтамасыз етілген жылдық сұраныс бөлігін көрсетеді."))


def economics(api: PlanningService) -> None:
    page_header(loc("Экономика планирования", "Жоспарлау экономикасы"), loc("Экономика", "Экономика"), loc("Сравните стоимостные результаты планирования для эталона Родина.", "Родина эталоны үшін жоспарлау құнының нәтижелерін салыстырыңыз."), [(loc("СПРАВОЧНЫЕ ЗАТРАТЫ", "АНЫҚТАМАЛЫҚ ШЫҒЫНДАР"), "success"), (loc("ПЛАНОВАЯ ОЦЕНКА", "ЖОСПАРЛЫҚ БАҒА"), "info")])
    target = target_selector("economics_target"); selected = api.design(target)
    section_header(loc("Экономика конфигурации {target:.0%}", "{target:.0%} конфигурациясының экономикасы", target=target))
    a, b, c, d = st.columns(4)
    with a: metric(loc("Начальные капзатраты", "Бастапқы күрделі шығындар"), money(selected["initial_capex_usd"]))
    with b: metric(loc("Чистая приведённая стоимость", "Таза дисконтталған құн"), money(selected["net_present_cost_usd"]), help_key="npc")
    with c: metric(loc("Эквивалентные годовые затраты", "Баламалы жылдық шығын"), money(selected["equivalent_annual_cost_usd"]) + loc("/год", "/жыл"), help_key="eac")
    with d: metric(loc("Стоимость обслуженного кВт·ч", "Өтелген кВт·сағ құны"), f"${selected['cost_per_served_kwh_usd']:.3f}")
    rows = []
    for value in (0.95, 0.99):
        design = api.design(value); rows.append({"target": f"{value:.0%}", "CAPEX": design["initial_capex_usd"], "NPC": design["net_present_cost_usd"], "EAC": design["equivalent_annual_cost_usd"]})
    frame = pd.DataFrame(rows)
    section_header(loc("Сравнение стоимости", "Құнды салыстыру"), loc("Показаны только итоги: проверенная разбивка затрат по компонентам не публикуется.", "Тек қорытындылар көрсетілген: компоненттер бойынша тексерілген шығын бөлінісі жарияланбайды."))
    left, right = st.columns(2)
    with left: st.altair_chart(bar_chart(frame, "target", "NPC", y_title="Net present cost (USD)", color=COLORS["primary"]), width="stretch")
    with right: st.altair_chart(bar_chart(frame, "target", "EAC", y_title="Equivalent annual cost (USD/year)", color=COLORS["storage"]), width="stretch")
    lower, higher = api.design(0.95), api.design(0.99); change = 100 * (higher["net_present_cost_usd"] / lower["net_present_cost_usd"] - 1)
    callout(loc("Интерпретация стоимости Родины", "Родина құнын түсіндіру"), loc("Цель 99% увеличивает моделируемую ЧДД жизненного цикла на {change:.1f}% относительно цели 95% при зафиксированных допущениях.", "99% мақсаты бекітілген болжамдарда 95% мақсатымен салыстырғанда модельденген өмірлік циклдің таза дисконтталған құнын {change:.1f}% арттырады.", change=change))
    st.caption(loc("Для ФЭ используется итоговый масштабно-зависимый экономический класс. Цена накопителя — справочная методика, а не коммерческое предложение.", "ФЭ үшін қорытынды масштабқа тәуелді экономикалық класс қолданылады. Жинақтау жүйесінің бағасы — сатып алу ұсынысы емес, анықтамалық әдіс."))


def sensitivity(api: PlanningService) -> None:
    page_header(loc("Анализ · Устойчивость", "Талдау · Тұрақтылық"), loc("Чувствительность", "Сезімталдық"), loc("Проверьте, какие детерминированные изменения сохраняют или нарушают цель каждой конфигурации.", "Қай детерминирленген өзгерістер әр конфигурацияның мақсатын сақтайтынын немесе бұзатынын тексеріңіз."), [(loc("ДЕТЕРМИНИРОВАННЫЙ", "ДЕТЕРМИНИРЛЕНГЕН"), "warning"), (loc("НЕ ВЕРОЯТНОСТНЫЙ", "ЫҚТИМАЛДЫҚ ЕМЕС"), "warning")])
    target = target_selector("sensitivity_target"); frame = pd.DataFrame(api.fixed_sensitivity_rows(target))
    section_header(loc("Физические сценарии", "Физикалық сценарийлер"), loc("Пунктирный порог и явный статус показывают прохождение без опоры только на цвет.", "Үзік шек пен нақты мәртебе нәтижені тек түске сүйенбей көрсетеді."))
    st.altair_chart(sensitivity_chart(frame, target), width="stretch")
    scenario_names = [name for name in ("demand_low", "nominal", "demand_high", "pv_low", "pv_high", "wind_shear_low", "wind_shear_high", "resource_favorable", "resource_stress") if name in set(frame["scenario"])]
    selected_name = st.selectbox(loc("Изучить сценарий", "Сценарийді зерттеу"), scenario_names, format_func=readable)
    selected = frame.loc[frame["scenario"] == selected_name].iloc[0]; status = "MEETS TARGET" if selected["passes_target"] else "BELOW TARGET"
    callout(status, f"{readable(selected_name)} serves {percent(selected['served_fraction'], 3)} of annual demand, with {selected['loss_of_load_hours']} loss-of-load hours and a {selected['longest_deficit_hours']}-hour longest deficit.", "info" if selected["passes_target"] else "critical")
    section_header(loc("Запасы устойчивости", "Тұрақтылық қоры"), loc("Номинальные системы минимальной стоимости находятся близко к ограничениям надёжности.", "Ең төмен құнды номиналды жүйелер сенімділік шектеріне жақын."))
    margins = next(row for row in api.margin_rows() if row["target"] == target)
    a, b, c = st.columns(3)
    headroom = 100 * (margins["maximum_demand_multiplier_for_target"] - 1)
    with a: metric(loc("Запас по спросу", "Сұраныс қоры"), f"+{headroom:.2f}%")
    with b: metric(loc("Минимальный множитель ФЭ", "Ең төмен ФЭ көбейткіші"), f"{margins['minimum_pv_multiplier_for_target']:.4f}×")
    with c: metric(loc("Максимально допустимый сдвиг α", "Ең жоғары рұқсат етілген ығысу α"), f"{margins['maximum_wind_shear_for_target']:.4f}")
    callout(loc("Малый запас надёжности", "Сенімділік қоры аз"), loc("Номинальная конфигурация {target:.0%} допускает лишь около +{headroom:.2f}% дополнительного годового спроса.", "Номиналды {target:.0%} конфигурациясы жылдық сұраныстың шамамен +{headroom:.2f}% қосымша өсуіне ғана шыдайды.", target=target, headroom=headroom), "warning")
    with st.expander("Economic one-factor scenarios"):
        economic = frame.loc[frame["varied_assumption"].isin(["wind_capex_multiplier", "pv_capex_multiplier", "battery_capex_multiplier"]), ["scenario", "net_present_cost_usd", "equivalent_annual_cost_usd", "served_fraction"]]
        st.dataframe(economic, hide_index=True, width="stretch")
    st.info(loc("Сценарии чувствительности — детерминированные исследовательские возмущения, а не вероятностные прогнозы.", "Сезімталдық сценарийлері — ықтималдық болжамдары емес, детерминирленген зерттеу өзгерістері."))
    st.caption(loc("Большее α неблагоприятно, поскольку ступицы всех моделируемых турбин ниже опорной высоты ERA5 100 м.", "Үлкен α қолайсыз, өйткені барлық модельденген турбиналардың түпкі биіктігі ERA5-тің 100 м тірек биіктігінен төмен."))


def methodology(api: PlanningService) -> None:
    page_header(loc("МЕТОД ПЛАТФОРМЫ", "ПЛАТФОРМА ӘДІСІ"), loc("Как работает SteppeGrid", "SteppeGrid қалай жұмыс істейді"), loc("От почасовых данных площадки к прозрачному результату планирования микросети.", "Алаңның сағаттық деректерінен микрожеліні жоспарлаудың ашық нәтижесіне дейін."), [(loc("ПОЧАСОВОЙ", "САҒАТТЫҚ"), "success"), (loc("ВОСПРОИЗВОДИМЫЙ", "ҚАЙТА ӨНДІРІЛЕТІН"), "info")])
    sections = [
        (loc("1. Площадка и погода", "1. Алаң және ауа райы"), loc("Каждое село представлено координатами и кэшированным годом почасовой погоды ERA5.", "Әр ауыл координаттармен және кэштелген бір жылдық ERA5 сағаттық ауа райымен ұсынылған.")),
        (loc("2. Спрос на электроэнергию", "2. Электр энергиясына сұраныс"), loc("Годовой, месячный или загруженный почасовой спрос представлен рядом из 8 760 часов.", "Жылдық, айлық немесе жүктелген сағаттық сұраныс 8 760 сағаттық қатармен ұсынылған.")),
        (loc("3. Ветер", "3. Жел"), loc("Ветер на высоте ступицы рассчитывается из погодного профиля и кривых мощности турбин.", "Түпкі биіктігіндегі жел ауа райы профилі мен турбина қуатының қисықтары арқылы есептеледі.")),
        (loc("4. Солнце", "4. Күн"), loc("Облучённость преобразуется в выработку наклонного ФЭ-массива и ограничивается инвертором.", "Сәулелену көлбеу ФЭ-массив өндіруіне айналып, инвертормен шектеледі.")),
        (loc("5. Накопитель", "5. Жинақтау жүйесі"), loc("Заряд, разряд, КПД, ограничения мощности и состояние заряда отслеживаются каждый час.", "Заряд, разряд, ПӘК, қуат шектері және заряд күйі әр сағат сайын бақыланады.")),
        (loc("6. Почасовая диспетчеризация", "6. Сағаттық диспетчерлеу"), loc("ВИЭ сначала питают нагрузку; накопитель принимает избыток и покрывает дефицит.", "ЖЭК алдымен жүктемені өтейді; жинақтау жүйесі артығын қабылдап, тапшылықты жабады.")),
        (loc("7. Надёжность", "7. Сенімділік"), loc("SteppeGrid сообщает обслуженную энергию, дефицит, часы потери нагрузки и длительность дефицита — не время безотказной работы.", "SteppeGrid өтелген энергияны, тапшылықты, жүктемені жоғалту сағаттарын және тапшылық ұзақтығын көрсетеді — үздіксіз жұмыс уақытын емес.")),
        (loc("8. Оптимизация", "8. Оңтайландыру"), loc("Дискретный поиск подбирает ветер, солнце и накопитель под выбранную годовую цель.", "Дискретті іздеу таңдалған жылдық мақсатқа жел, күн және жинақтау жүйесін таңдайды.")),
        (loc("9. Экономика", "9. Экономика"), loc("Капзатраты, ЧДД, годовые затраты и стоимость обслуженного кВт·ч поддерживают сравнение.", "Күрделі шығындар, таза дисконтталған құн, жылдық шығын және өтелген кВт·сағ құны салыстыруды қолдайды.")),
        (loc("10. Сравнение сёл", "10. Ауылдарды салыстыру"), loc("Нормированные по спросу показатели позволяют последовательно сравнивать сёла разного размера.", "Сұраныс бойынша нормаланған көрсеткіштер әртүрлі көлемдегі ауылдарды жүйелі салыстыруға мүмкіндік береді.")),
    ]
    for title, body in sections:
        section_header(title)
        st.write(body)


ROUTES = {
    "Overview": overview, "Demand & Weather": demand_weather, "Renewable Generation": renewable_generation,
    "System Design": system_design, "Reliability": reliability, "Economics": economics,
    "Sensitivity": sensitivity, "Methodology & Provenance": methodology,
}

if "active_page" not in st.session_state:
    st.session_state.active_page = "Overview"
elif st.session_state.active_page not in ROUTES:
    st.session_state.active_page = "Overview"
if "app_mode" not in st.session_state:
    st.session_state.app_mode = "Explore Benchmark"
pending_destination = st.session_state.pop("_pending_primary_destination", None)
if st.session_state.get("primary_navigation") not in PRIMARY_DESTINATIONS:
    st.session_state.primary_navigation = "Overview"
if pending_destination in PRIMARY_DESTINATIONS:
    st.session_state.primary_navigation = pending_destination
language_switch()
app_header()
primary_destination = st.segmented_control(
    tr("Primary navigation"),
    PRIMARY_DESTINATIONS,
    key="primary_navigation",
    format_func=lambda destination: tr(destination),
    label_visibility="collapsed",
)
if primary_destination is None:
    primary_destination = "Overview"
if primary_destination == "Research":
    current_research_page = st.session_state.active_page if st.session_state.active_page in RESEARCH_PAGES else RESEARCH_PAGES[0]
    if st.session_state.get("research_navigation") not in RESEARCH_PAGES:
        st.session_state.research_navigation = current_research_page
    research_page = st.segmented_control(
        tr("Research page"),
        RESEARCH_PAGES,
        key="research_navigation",
        format_func=lambda page: tr("How SteppeGrid Works") if page == "Methodology & Provenance" else tr(page),
        label_visibility="collapsed",
    )
    st.session_state.active_page = research_page or RESEARCH_PAGES[0]

MODE_BY_DESTINATION = {
    "Overview": "Explore Benchmark",
    "Sites": "Sites",
    "Plan a System": "Plan a System",
    "Compare": "Compare Sites",
    "Research": "Explore Benchmark",
}
st.session_state.app_mode = MODE_BY_DESTINATION[primary_destination]

try:
    if primary_destination == "Plan a System":
        render_planner(scenario_service(), site_registry())
    elif primary_destination == "Sites":
        render_sites(site_registry())
    elif primary_destination == "Compare":
        render_compare_sites(site_registry())
    elif primary_destination == "Research":
        ROUTES[st.session_state.active_page](service())
    else:
        overview(service())
except AppDataError as error:
    st.error(str(error))
    st.code("python scripts/run_phase12.py --mode verify", language="powershell")
    st.stop()
