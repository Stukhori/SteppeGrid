"""Streamlit workflow for catalog-versioned user planning scenarios."""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta

import pandas as pd
import streamlit as st
from pydantic import ValidationError

from steppegrid.app.components import callout, metric, page_header, section_header
from steppegrid.app.formatting import energy, money, percent, readable
from steppegrid.app.i18n import loc
from steppegrid.equipment.catalog import PLANNER_V2
from steppegrid.equipment.models import ProjectScale
from steppegrid.planning.demand import PlanningDemandError, demand_preview, parse_hourly_demand_csv
from steppegrid.planning.models import (
    DemandConfidence,
    DemandMode,
    DemandSourceType,
    DemandSpecification,
    CatalogFilterMode,
    PlanningScenario,
    PlanningSite,
    SitePreset,
    TechnologySelection,
)
from steppegrid.planning.service import PlanningRun, ScenarioPlanningService
from steppegrid.sites import SiteRegistry
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
WIND_TURBINES = PLANNER_V2.wind_turbines
PV_MODULES = PLANNER_V2.pv_modules
INVERTERS = PLANNER_V2.inverters
BATTERIES = PLANNER_V2.batteries


def _demand_mode_label(value: DemandMode | str) -> str:
    labels = {
        "registered_dataset": ("Существующий зарегистрированный набор данных", "Тіркелген қолданыстағы деректер жинағы"),
        DemandMode.RODINA_BENCHMARK.value: ("Эталонный спрос Родины", "Родина эталондық сұранысы"),
        DemandMode.ESTIMATED_ANNUAL.value: ("Оценка годового спроса", "Жылдық сұраныс бағасы"),
        DemandMode.ESTIMATED_MONTHLY.value: ("Оценка месячного спроса", "Айлық сұраныс бағасы"),
        DemandMode.HOURLY_UPLOAD.value: ("Загрузка почасового спроса", "Сағаттық сұранысты жүктеу"),
    }
    key = value if isinstance(value, str) else value.value
    return loc(*labels.get(key, (readable(key), readable(key))))


def _shape_label(value: str) -> str:
    labels = {
        "community_facility_like": ("Общественные объекты", "Қоғамдық нысандар"),
        "residential_like": ("Жилой профиль", "Тұрғын үй профилі"),
        "flat_within_month": ("Равномерно внутри месяца", "Ай ішінде біркелкі"),
    }
    return loc(*labels[value])


def result_is_stale(result, scenario: PlanningScenario | None) -> bool:
    return scenario is None or result.scenario_input_hash != scenario.input_hash


def _source_configuration(mode: DemandMode) -> tuple[DemandSourceType, DemandConfidence]:
    if mode is DemandMode.RODINA_BENCHMARK:
        return DemandSourceType.SOURCE_RECONSTRUCTED, DemandConfidence.STRONG_SOURCE_RECONSTRUCTION
    return DemandSourceType.USER_PROVIDED, DemandConfidence.USER_PROVIDED_UNVERIFIED


def _build_inputs(registry: SiteRegistry) -> tuple[PlanningScenario | None, object | None, str | None]:
    section_header(
        loc("1 · Площадка", "1 · Алаң"),
        loc("Выберите зарегистрированное село или временные пользовательские координаты.", "Тіркелген ауылды немесе уақытша пайдаланушы координаттарын таңдаңыз."),
    )
    # Keep the established benchmark as the neutral landing state while exposing
    # every registered village. This ordering is not a site recommendation.
    classification_order = {"BENCHMARK": 0, "FIELD_CASE": 1, "PLANNING_SITE": 2}
    sites = sorted(
        registry.list_sites(),
        key=lambda site: (classification_order.get(site.classification.value, 99), site.name.casefold()),
    )
    options = {
        ("Rodina benchmark site" if site.site_id == "rodina" else site.name): site.site_id
        for site in sites
    }
    options["Custom coordinates"] = None
    pending_site_id = st.session_state.pop("_pending_planner_site_id", None)
    pending_label = next(
        (label for label, site_id in options.items() if site_id == pending_site_id),
        None,
    ) if pending_site_id is not None else None
    if pending_label is not None:
        st.session_state["planner_site"] = pending_label
    site_label = st.selectbox(
        loc("Шаблон площадки", "Алаң үлгісі"),
        list(options),
        format_func=lambda value: (
            loc("Эталонная площадка Родина", "Родина эталондық алаңы") if value == "Rodina benchmark site"
            else loc("Пользовательские координаты", "Пайдаланушы координаттары") if value == "Custom coordinates"
            else value
        ),
        key="planner_site",
    )
    selected_site_id = options[site_label]
    registered_site = registry.get_site(selected_site_id) if selected_site_id else None
    if registered_site is None:
        name = st.text_input(loc("Название площадки", "Алаң атауы"), value=loc("Пользовательская площадка", "Пайдаланушы алаңы"), key="planner_site_name")
        latitude = st.number_input(loc("Широта", "Ендік"), min_value=-90.0, max_value=90.0, value=50.0, format="%.6f")
        longitude = st.number_input(loc("Долгота", "Бойлық"), min_value=-180.0, max_value=180.0, value=67.0, format="%.6f")
        timezone_offset = st.text_input(loc("Фиксированное смещение UTC", "Тұрақты UTC ығысуы"), value="+05:00")
        try:
            planning_site = PlanningSite(
                preset=SitePreset.CUSTOM, name=name, latitude=latitude,
                longitude=longitude, timezone_offset=timezone_offset,
            )
        except ValidationError as error:
            return None, None, str(error)
    else:
        planning_site = registry.planning_site(registered_site.site_id)
        name = registered_site.name
        st.caption(
            f"{registered_site.latitude:.6f}, {registered_site.longitude:.6f} · "
            f"{registered_site.timezone} · {registry.get_planning_readiness(registered_site.site_id).value}"
        )
    st.info(loc(
        "Погода: почасовой реанализ Open-Meteo ERA5 за 2025 год. Онлайн-запрос выполняется только после запуска планировщика, если точного кэша нет.",
        "Ауа райы: Open-Meteo ERA5 жүйесінің 2025 жылғы сағаттық реанализі. Дәл кэш болмаса, онлайн сұрау жоспарлағыш іске қосылғаннан кейін ғана орындалады.",
    ))

    section_header(loc("2 · Спрос", "2 · Сұраныс"), loc("Укажите величину спроса, временной профиль и класс данных.", "Сұраныс көлемін, уақыт профилін және деректер класын көрсетіңіз."))
    allowed_modes: list[DemandMode | str] = [DemandMode.ESTIMATED_ANNUAL, DemandMode.ESTIMATED_MONTHLY, DemandMode.HOURLY_UPLOAD]
    if registered_site and registered_site.demand_datasets:
        allowed_modes.append("registered_dataset")
    if registered_site and registered_site.classification.value == "BENCHMARK":
        allowed_modes.insert(0, DemandMode.RODINA_BENCHMARK)
    mode = st.selectbox(
        loc("Сценарий спроса", "Сұраныс сценарийі"), allowed_modes,
        format_func=_demand_mode_label,
        key="planner_demand_mode",
    )
    shape = "community_facility_like"
    if mode != "registered_dataset":
        shape = st.selectbox(
            loc("Детерминированный почасовой профиль", "Детерминирленген сағаттық профиль"),
            ["community_facility_like", "residential_like", "flat_within_month"],
            format_func=_shape_label, key="planner_shape", disabled=mode is DemandMode.HOURLY_UPLOAD,
        )
    annual = None; monthly = None; uploaded = None
    upload_filename = upload_hash = None
    source_name = source_url = None; source_year = None
    demand_id = registered_demand_sha256 = None
    registered_specification = None
    if mode == "registered_dataset":
        assert registered_site is not None
        demand_options = {item.name: item.demand_id for item in registered_site.demand_datasets}
        demand_label = st.selectbox(loc("Зарегистрированный набор спроса", "Тіркелген сұраныс деректері"), list(demand_options), key="planner_registered_demand")
        demand_id = demand_options[demand_label]
        dataset = registry.get_demand_dataset(registered_site.site_id, demand_id)
        registered_demand_sha256 = dataset.demand_sha256
        registered_specification = registry.demand_specification(registered_site.site_id, demand_id)
        uploaded = registry.build_demand(registered_site.site_id, demand_id)
        st.caption(loc("Годовой спрос: {value}", "Жылдық сұраныс: {value}", value=energy(dataset.annual_energy_kwh)))
        source_type, confidence, method = dataset.classification, dataset.confidence, dataset.profile_method
        shape = dataset.profile_shape
    elif mode is DemandMode.RODINA_BENCHMARK:
        source_type, confidence = _source_configuration(mode)
        method = "Frozen Phase 9 literature monthly-row reconstruction"
    elif mode is DemandMode.HOURLY_UPLOAD:
        source_type = DemandSourceType.USER_PROVIDED
        confidence = DemandConfidence.USER_PROVIDED_UNVERIFIED
        upload = st.file_uploader(loc("Почасовой CSV", "Сағаттық CSV"), type="csv", help=loc("Точные столбцы: timestamp,demand_kwh. Значения — кВт·ч за каждый час.", "Нақты бағандар: timestamp,demand_kwh. Мәндер — әр сағаттағы кВт·сағ."))
        method = st.text_input(loc("Метод спроса / примечание об источнике", "Сұраныс әдісі / дереккөз ескертпесі"), value=loc("Пользовательский CSV с почасовым спросом", "Пайдаланушының сағаттық сұраныс CSV файлы"))
        if upload is not None:
            payload = upload.getvalue(); upload_filename = upload.name
            upload_hash = hashlib.sha256(payload).hexdigest()
            try:
                uploaded = parse_hourly_demand_csv(payload, source_type=source_type, confidence=confidence, method=method, source_name=upload.name)
            except PlanningDemandError as error:
                return None, None, str(error)
    else:
        source_type, confidence = _source_configuration(mode)
        if mode is DemandMode.ESTIMATED_ANNUAL:
            annual = st.number_input(
                loc("Оценочный годовой спрос (кВт·ч/год)", "Болжамды жылдық сұраныс (кВт·сағ/жыл)"), min_value=10_000.0,
                max_value=20_000_000.0, value=None, step=10_000.0,
                help=loc("Обязательное поле. SteppeGrid не подставляет оценку спроса площадки.", "Міндетті өріс. SteppeGrid алаң сұранысының бағасын автоматты түрде қоймайды."),
            )
        else:
            st.caption(loc("Введите суммарное потребление за каждый из 12 месяцев в кВт·ч.", "12 айдың әрқайсысы үшін жиынтық тұтынуды кВт·сағ түрінде енгізіңіз."))
            values = []
            for start in range(0, 12, 4):
                columns = st.columns(4)
                for column, month in zip(columns, MONTHS[start:start + 4], strict=True):
                    with column:
                        values.append(st.number_input(month, min_value=0.0, value=0.0, step=1_000.0, key=f"planner_month_{month}"))
            monthly = tuple(values)
        source_name = st.text_input(loc("Название источника оценки или аналога", "Бағалау немесе ұқсас дереккөз атауы"), value="", help=loc("Обязательно для спроса по аналогу; необязательно для пользовательской синтетической оценки.", "Ұқсас деректерге негізделген сұраныс үшін міндетті; пайдаланушының синтетикалық бағасы үшін міндетті емес.")) or None
        source_url = st.text_input(loc("URL источника (необязательно)", "Дереккөз URL-і (міндетті емес)"), value="") or None
        source_year_value = st.number_input(loc("Год источника (необязательно; 0 = неизвестно)", "Дереккөз жылы (міндетті емес; 0 = белгісіз)"), min_value=0, max_value=9998, value=0)
        source_year = int(source_year_value) or None
        method = st.text_area(loc("Метод оценки", "Бағалау әдісі"), value=loc("Заданная пользователем оценка энергии, распределённая по детерминированному профилю планирования.", "Пайдаланушы белгілеген энергия бағасы детерминирленген жоспарлау профилі бойынша таратылды."))

    section_header(loc("3 · Надёжность", "3 · Сенімділік"), loc("Выберите долю обслуженной годовой энергии; это не показатель времени безотказной работы.", "Қамтылатын жылдық энергия үлесін таңдаңыз; бұл үздіксіз жұмыс уақытының көрсеткіші емес."))
    target_label = st.segmented_control(loc("Целевая доля обслуженной энергии", "Қамтылатын энергияның мақсатты үлесі"), ["95%", "99%"], default="95%", key="planner_target")
    target = 0.95 if target_label == "95%" else 0.99
    section_header(loc("4 · Технологии", "4 · Технологиялар"), loc("Ограничьте поиск оборудованием из каталога с указанными источниками.", "Іздеуді дереккөздері көрсетілген каталог жабдықтарымен шектеңіз."))
    filter_mode = st.selectbox(
        loc("Фильтр каталога", "Каталог сүзгісі"), list(CatalogFilterMode), index=0,
        format_func=lambda value: readable(value.value),
        help=loc("Все проверенное оборудование охватывает полный каталог V2. Другие фильтры явно сохраняются во входных данных сценария.", "Барлық тексерілген жабдық толық V2 каталогын қамтиды. Басқа сүзгілер сценарийдің кіріс деректерінде нақты сақталады."),
    )
    if filter_mode is CatalogFilterMode.SMALL_COMMUNITY:
        scales = (ProjectScale.SMALL_COMMUNITY, ProjectScale.COMMUNITY)
    elif filter_mode is CatalogFilterMode.MEDIUM_LARGE:
        scales = (ProjectScale.COMMERCIAL, ProjectScale.UTILITY)
    else:
        scales = tuple(ProjectScale)
    eligible_wind = [key for key, item in WIND_TURBINES.items() if item.scale_class in scales]
    eligible_inverters = [key for key, item in INVERTERS.items() if item.scale_class in scales]
    eligible_batteries = [key for key, item in BATTERIES.items() if item.scale_class in scales]
    pv_options = [f"{module}__{inverter}" for module in PV_MODULES for inverter in INVERTERS]
    eligible_pv = [key for key in pv_options if key.split("__", 1)[1] in eligible_inverters]
    if filter_mode is CatalogFilterMode.CUSTOM:
        wind_keys = tuple(st.multiselect(loc("Ветротурбины", "Жел турбиналары"), list(WIND_TURBINES), default=["sd6"], format_func=readable))
        pv_keys = tuple(st.multiselect(loc("Блоки фотоэлектрических модулей и инверторов", "Фотоэлектрлік модуль және инвертор блоктары"), pv_options, default=["trina_tsm_450_neg9r28__sma_core1_stp50_41"], format_func=readable))
        battery_keys = tuple(st.multiselect(loc("Аккумуляторные системы", "Аккумулятор жүйелері"), list(BATTERIES), default=["sungrow_powerstack_st255_2h"], format_func=readable))
    else:
        wind_keys, pv_keys, battery_keys = tuple(eligible_wind), tuple(eligible_pv), tuple(eligible_batteries)
        st.caption(loc("Фильтр включает {wind} моделей ветротурбин, {pv} конфигураций ФЭМ и {battery} аккумуляторных систем.", "Сүзгіге {wind} жел турбинасы моделі, {pv} ФЭМ конфигурациясы және {battery} аккумулятор жүйесі кіреді.", wind=len(wind_keys), pv=len(pv_keys), battery=len(battery_keys)))
    with st.expander(loc("Каталог и сведения о технологиях", "Каталог және технологиялар туралы мәлімет")):
        details = []
        for key in wind_keys:
            item = WIND_TURBINES[key]
            details.append({"Technology": key, "Type": "Wind", "Rated scale": f"{item.rated_power_kw:g} kW", "Planning hub height": f"{item.planning_hub_height_m or item.supported_hub_heights_m[0]:g} m", "Scale class": readable(item.scale_class.value), "Source": item.provenance[0].source_url})
        for key in pv_keys:
            module_key, inverter_key = key.split("__", 1)
            inverter = INVERTERS[inverter_key]
            details.append({"Technology": key, "Type": "PV block", "Rated scale": f"{inverter.rated_ac_power_kw:g} kWac", "Planning hub height": "—", "Scale class": readable(inverter.scale_class.value), "Source": inverter.provenance[0].source_url})
        for key in battery_keys:
            item = BATTERIES[key]
            details.append({"Technology": key, "Type": "Battery", "Rated scale": f"{item.usable_energy_capacity_kwh:g} kWh / {item.maximum_discharge_power_kw:g} kW", "Planning hub height": "—", "Scale class": readable(item.scale_class.value), "Source": item.provenance[0].source_url})
        st.dataframe(pd.DataFrame(details), hide_index=True, width="stretch")
    scenario_name = st.text_input(loc("Название сценария", "Сценарий атауы"), value=loc("Сценарий планирования: {name}", "Жоспарлау сценарийі: {name}", name=name))
    try:
        specification = registered_specification or DemandSpecification(
            mode=mode, source_type=source_type, confidence=confidence,
            profile_shape=shape, annual_kwh=annual, monthly_kwh=monthly,
            source_name=source_name, source_url=source_url, source_year=source_year,
            method_notes=method, upload_filename=upload_filename, upload_sha256=upload_hash,
        )
        scenario = PlanningScenario(
            name=scenario_name,
            site=planning_site,
            demand=specification, reliability_target=target,
            demand_id=demand_id, registered_demand_sha256=registered_demand_sha256,
            technologies=TechnologySelection(wind_keys=wind_keys, pv_keys=pv_keys, battery_keys=battery_keys, filter_mode=filter_mode, scale_classes=scales),
        )
    except (ValidationError, ValueError) as error:
        return None, uploaded, str(error)
    return scenario, uploaded, None


def _render_result(run: PlanningRun) -> None:
    result = run.result
    section_header(loc("Результат планирования", "Жоспарлау нәтижесі"), loc("Этот результат относится только к указанному ниже сценарию с контрольной суммой.", "Бұл нәтиже тек төмендегі бақылау сомасы бар сценарийге тиесілі."))
    if not result.feasible or result.design is None:
        callout(loc("Подходящий проект не найден", "Сәйкес жоба табылмады"), loc("Ограниченный поиск не нашёл портфель, соответствующий выбранной цели.", "Шектелген іздеу таңдалған мақсатқа сәйкес портфель таппады."), "critical")
        return
    design = result.design
    a, b, c, d = st.columns(4)
    metrics = result.metrics; economics = result.economics
    assert metrics is not None and economics is not None
    st.info(loc(
        "Площадка: {site} · Спрос: {demand} · Каталог: {catalog} · Экономика: {economics} · рассмотрено: {wind} ветровых, {pv} ФЭМ и {battery} аккумуляторных вариантов.",
        "Алаң: {site} · Сұраныс: {demand} · Каталог: {catalog} · Экономика: {economics} · қарастырылды: {wind} жел, {pv} ФЭМ және {battery} аккумулятор нұсқасы.",
        site=result.site_id or loc("временная пользовательская", "уақытша пайдаланушы"), demand=result.demand_id or loc("входные данные сценария", "сценарий кірісі"),
        catalog=result.equipment_catalog_version.value, economics=result.economics_version.value,
        wind=result.catalog_option_counts.get("wind", 0), pv=result.catalog_option_counts.get("pv", 0), battery=result.catalog_option_counts.get("battery", 0),
    ))
    callout(
        loc("Расчётный результат планирования", "Есептік жоспарлау нәтижесі") if result.demand_source_type is not DemandSourceType.MEASURED else loc("Результат по измеренному спросу", "Өлшенген сұраныс нәтижесі"),
        loc("Основа спроса: {source} · {confidence}. Модель включает {wind:,.1f} кВт ветра, {pv:,.1f} кВт ФЭМ и {battery:,.1f} кВт·ч полезной ёмкости, обеспечивая {served} смоделированной годовой энергии.", "Сұраныс негізі: {source} · {confidence}. Модельде {wind:,.1f} кВт жел, {pv:,.1f} кВт ФЭМ және {battery:,.1f} кВт·сағ пайдалы сыйымдылық бар; модельденген жылдық энергияның {served} қамтамасыз етіледі.", source=result.demand_source_type.value, confidence=result.demand_confidence.value, wind=design.wind_capacity_kw, pv=design.pv_ac_capacity_kw, battery=design.battery_usable_capacity_kwh, served=percent(metrics.served_fraction, 3)),
        "info",
    )
    with a: metric(loc("Обслуженный годовой спрос", "Қамтылған жылдық сұраныс"), percent(metrics.served_fraction, 3))
    with b: metric(loc("Недоотпущенная энергия", "Қамтылмаған энергия"), energy(metrics.unmet_energy_kwh))
    with c: metric(loc("Чистая приведённая стоимость", "Таза келтірілген құн"), money(economics.net_present_cost_usd))
    with d: metric(loc("Часы потери нагрузки", "Жүктеме жоғалған сағаттар"), f"{metrics.loss_of_load_hours:,} h")
    st.dataframe(pd.DataFrame([
        {"Technology": "Wind", "Selection": readable(design.wind_key) if design.wind_key else "None", "Count": design.wind_count, "Capacity": f"{design.wind_capacity_kw:,.1f} kW"},
        {"Technology": "PV", "Selection": readable(design.pv_key) if design.pv_key else "None", "Count": design.pv_count, "Capacity": f"{design.pv_ac_capacity_kw:,.1f} kWac"},
        {"Technology": "Storage", "Selection": readable(design.battery_key) if design.battery_key else "None", "Count": design.battery_count, "Capacity": f"{design.battery_usable_capacity_kwh:,.1f} kWh usable"},
    ]), hide_index=True, width="stretch")
    st.caption(f"Method: {readable(result.optimizer_method)} · {result.theoretical_design_combinations:,} theoretical combinations · {result.evaluated_portfolios:,} renewable portfolios · {result.dispatch_simulations:,} dispatch simulations · {result.dispatch_cache_hits:,} cache hits · {result.elapsed_seconds:.2f} s")
    st.caption(
        f"Longest deficit: {metrics.longest_deficit_hours:,} h · maximum hourly deficit: "
        f"{metrics.maximum_hourly_deficit_kwh:,.1f} kWh · curtailment: {energy(metrics.curtailment_kwh)} · "
        f"CAPEX: {money(economics.initial_capex_usd)} · EAC: {money(economics.equivalent_annual_cost_usd)}/year · "
        f"planning cost per served kWh: ${economics.cost_per_served_kwh_usd:.3f}"
    )
    dispatch = pd.DataFrame(run.dispatch_rows); dispatch["timestamp"] = pd.to_datetime(dispatch["timestamp"])
    window_labels = {
        "First week": ("Первая неделя", "Бірінші апта"),
        "Highest-unmet week": ("Неделя с наибольшим дефицитом", "Ең үлкен тапшылық аптасы"),
        "Highest-curtailment week": ("Неделя с наибольшим ограничением", "Ең үлкен шектеу аптасы"),
    }
    window = st.selectbox(loc("Период диспетчеризации", "Диспетчерлеу кезеңі"), list(window_labels), format_func=lambda value: loc(*window_labels[value]))
    if window == "First week":
        start = dispatch["timestamp"].iloc[0]
    else:
        column = "unmet_energy_kwh" if window == "Highest-unmet week" else "curtailment_kwh"
        start = dispatch.loc[dispatch[column].idxmax(), "timestamp"] - timedelta(days=3)
    viewed = dispatch.loc[(dispatch["timestamp"] >= start) & (dispatch["timestamp"] < start + timedelta(days=7))]
    st.line_chart(viewed.set_index("timestamp")[["demand_kwh", "renewable_generation_kwh", "served_energy_kwh"]])
    st.area_chart(viewed.set_index("timestamp")[["battery_soc_end_kwh", "unmet_energy_kwh", "curtailment_kwh"]])
    export_json = json.dumps({"scenario": run.scenario.model_dump(mode="json"), "result": result.model_dump(mode="json")}, indent=2, sort_keys=True)
    summary_csv = pd.DataFrame([{
        "scenario_id": result.scenario_id, "scenario_input_hash": result.scenario_input_hash,
        "site_id": result.site_id, "site_metadata_hash": result.site_metadata_hash,
        "demand_id": result.demand_id,
        "equipment_catalog_version": result.equipment_catalog_version.value,
        "economics_version": result.economics_version.value,
        "demand_sha256": result.demand_sha256, "weather_sha256": result.weather_sha256,
        "demand_source_type": result.demand_source_type.value,
        "demand_confidence": result.demand_confidence.value,
        "annual_demand_kwh": result.annual_demand_kwh, "target": result.reliability_target,
        "wind_key": design.wind_key, "wind_count": design.wind_count,
        "pv_key": design.pv_key, "pv_count": design.pv_count,
        "battery_key": design.battery_key, "battery_count": design.battery_count,
        "served_fraction": metrics.served_fraction,
        "unmet_energy_kwh": metrics.unmet_energy_kwh,
        "loss_of_load_hours": metrics.loss_of_load_hours,
        "curtailment_kwh": metrics.curtailment_kwh,
        "initial_capex_usd": economics.initial_capex_usd,
        "net_present_cost_usd": economics.net_present_cost_usd,
        "equivalent_annual_cost_usd": economics.equivalent_annual_cost_usd,
    }]).to_csv(index=False)
    left, right = st.columns(2)
    with left: st.download_button(loc("Скачать результат JSON", "JSON нәтижесін жүктеу"), export_json, f"{result.scenario_id}.json", "application/json")
    with right: st.download_button(loc("Скачать результат CSV", "CSV нәтижесін жүктеу"), summary_csv, f"{result.scenario_id}.csv", "text/csv")


def render_planner(api: ScenarioPlanningService, registry: SiteRegistry | None = None) -> None:
    registry = registry or api.registry
    page_header(
        loc("Интерактивное планирование", "Интерактивті жоспарлау"), loc("Спроектировать систему", "Жүйені жобалау"),
        loc("Выберите площадку, задайте спрос и надёжность, выберите технологии и оцените предложенную систему.", "Алаңды таңдап, сұраныс пен сенімділікті белгілеңіз, технологияларды таңдаңыз және ұсынылған жүйені бағалаңыз."),
        [(loc("ПОЛЬЗОВАТЕЛЬСКИЙ СЦЕНАРИЙ", "ПАЙДАЛАНУШЫ СЦЕНАРИЙІ"), "info"), (loc("ПОГОДА ERA5", "ERA5 АУА РАЙЫ"), "info"), (loc("ЯВНЫЙ ЗАПУСК", "НАҚТЫ ІСКЕ ҚОСУ"), "success")],
    )
    callout(loc("Границы модели планирования", "Жоспарлау моделінің шегі"), loc("Результат — смоделированный сценарий, а не подтверждённый на местности оптимум, коммерческое предложение, доверительный интервал или распределение вероятностей.", "Нәтиже — модельденген сценарий; ол жергілікті жерде расталған оптимум, коммерциялық ұсыныс, сенімділік аралығы немесе ықтималдық үлестірімі емес."), "warning")
    scenario, uploaded, error = _build_inputs(registry)
    section_header(loc("5 · Проверка и запуск", "5 · Тексеру және іске қосу"), loc("Контрольная сумма меняется при изменении любого входного параметра модели.", "Модельдің кез келген кіріс параметрі өзгерсе, бақылау сомасы да өзгереді."))
    if error:
        st.warning(error)
    elif scenario is not None:
        try:
            demand, weather = api.review(scenario, uploaded)
            preview = demand_preview(demand)
            a, b, c, d = st.columns(4)
            with a: metric(loc("Годовой спрос", "Жылдық сұраныс"), energy(float(preview["annual_kwh"])))
            with b: metric(loc("Пиковый почасовой спрос", "Сағаттық шекті сұраныс"), energy(float(preview["peak_hourly_kwh"])))
            with c: metric(loc("Погода", "Ауа райы"), loc("Готово", "Дайын") if weather["cache_available"] else loc("Будет подготовлено при запуске", "Іске қосқанда дайындалады"))
            with d: metric(loc("Коэффициент нагрузки", "Жүктеме коэффициенті"), percent(float(preview["load_factor"]), 1))
            st.bar_chart(pd.DataFrame({"month": MONTHS, "demand_kwh": preview["monthly_kwh"]}).set_index("month"))
            preview_frame = pd.DataFrame({"timestamp": demand.timestamps[:168], "demand_kwh": demand.demand_kwh[:168]}).set_index("timestamp")
            st.line_chart(preview_frame)
            st.caption(loc("ID сценария: `{scenario}` · SHA-256 входных данных: `{hash}`", "Сценарий ID: `{scenario}` · кіріс SHA-256: `{hash}`", scenario=scenario.scenario_id, hash=scenario.input_hash))
            if st.button(loc("Запустить планировщик", "Жоспарлағышты іске қосу"), type="primary", width="stretch"):
                with st.status(loc("Выполняется планирование…", "Жоспарлау орындалуда…"), expanded=True) as status:
                    run = api.run(scenario, uploaded, progress=st.write)
                    status.update(label=loc("Планирование завершено", "Жоспарлау аяқталды"), state="complete")
                st.session_state["planner_last_run"] = run
                st.session_state.setdefault("planner_history", []).append(run.result.model_dump(mode="json"))
        except Exception as run_error:
            st.error(str(run_error))
    run = st.session_state.get("planner_last_run")
    if isinstance(run, PlanningRun):
        if result_is_stale(run.result, scenario):
            st.warning(loc("После последнего запуска входные данные изменились. Показанный результат устарел; запустите планировщик снова.", "Соңғы іске қосудан кейін кіріс деректері өзгерді. Көрсетілген нәтиже ескірген; жоспарлағышты қайта іске қосыңыз."))
        _render_result(run)
    history = st.session_state.get("planner_history", [])
    if len(history) > 1:
        section_header(loc("Сравнение сеанса", "Сеансты салыстыру"), loc("Сравните результаты, созданные в этом сеансе браузера.", "Осы браузер сеансында жасалған нәтижелерді салыстырыңыз."))
        st.dataframe(pd.DataFrame([
            {"Scenario": row["scenario_name"], "Target": row["reliability_target"], "Annual demand (kWh)": row["annual_demand_kwh"], "Demand class": row["demand_source_type"], "Wind (kW)": row["design"]["wind_capacity_kw"] if row["design"] else None, "PV (kWac)": row["design"]["pv_ac_capacity_kw"] if row["design"] else None, "Storage (kWh)": row["design"]["battery_usable_capacity_kwh"] if row["design"] else None, "Served fraction": row["metrics"].get("served_fraction") if row["metrics"] else None, "LOLH": row["metrics"].get("loss_of_load_hours") if row["metrics"] else None, "Curtailment (kWh)": row["metrics"].get("curtailment_kwh") if row["metrics"] else None, "NPC (USD)": row["economics"].get("net_present_cost_usd") if row["economics"] else None, "Method": row["optimizer_method"]}
            for row in history
        ]), hide_index=True, width="stretch")
    if scenario is not None and scenario.site.site_id:
        persisted = registry.scenario_history(scenario.site.site_id)
        if persisted:
            section_header(loc("История сценариев площадки", "Алаң сценарийлерінің тарихы"), loc("Локальные исторические результаты сохраняют исходные контрольные суммы площадки и спроса.", "Жергілікті тарихи нәтижелер алаң мен сұраныстың бастапқы бақылау сомаларын сақтайды."))
            st.dataframe(pd.DataFrame(persisted), hide_index=True, width="stretch")
