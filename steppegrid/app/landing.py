"""A localized, read-only introduction to the saved village planning results."""
from base64 import b64encode
from functools import lru_cache
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

from steppegrid.app.i18n import current_language
from steppegrid.app.product import FEATURED_SITE_ID, latest_result, project_root
from steppegrid.sites import SiteRegistry


# English, Russian, Kazakh. Keep landing copy beside its visual components.
COPY = {
    "eyebrow": ("VILLAGE ENERGY PLANNING FOR KAZAKHSTAN", "ЭНЕРГОПЛАНИРОВАНИЕ СЁЛ КАЗАХСТАНА", "ҚАЗАҚСТАН АУЫЛДАРЫНЫҢ ЭНЕРГИЯСЫН ЖОСПАРЛАУ"),
    "title": ("What would it take to power a village?", "Что нужно, чтобы обеспечить село энергией?", "Ауылды энергиямен қамтамасыз ету үшін не қажет?"),
    "lead": ("Explore how local weather, electricity demand, and battery storage shape a renewable microgrid. See the equipment, the energy balance, and the cost—hour by hour.", "Узнайте, как местная погода, спрос и накопители определяют возобновляемую микросеть. Изучите оборудование, энергобаланс и стоимость — час за часом.", "Жергілікті ауа райы, электр сұранысы және жинақтау жүйесі жаңартылатын микрожеліні қалай анықтайтынын зерттеңіз. Жабдықты, энергия теңгерімін және құнын сағат сайын қараңыз."),
    "start": ("Start planning", "Начать планирование", "Жоспарлауды бастау"),
    "see_case": ("Explore the village case", "Изучить пример села", "Ауыл мысалын зерттеу"),
    "photo_title": ("Wind. Solar. Storage.", "Ветер. Солнце. Накопители.", "Жел. Күн. Жинақтау."),
    "photo_note": ("Kazakhstan renewable-energy sites · Context photos, not the modeled village", "Объекты ВИЭ Казахстана · Контекстные фото, не моделируемое село", "Қазақстанның ЖЭК нысандары · Модельденген ауылдың суреттері емес"),
    "villages": ("registered villages", "зарегистрированных сёл", "тіркелген ауыл"),
    "hours": ("hourly steps in one year", "часовых шагов за год", "бір жылдағы сағаттық қадам"),
    "targets": ("annual energy-served targets", "цели годового энергообеспечения", "жылдық энергияны қамту мақсаттары"),
    "technologies": ("wind, solar, and storage", "ветер, солнце и накопители", "жел, күн және жинақтау"),
    "workflow_kicker": ("FROM A PLACE TO A PLAN", "ОТ ПЛОЩАДКИ К ПЛАНУ", "ОРЫННАН ЖОСПАРҒА ДЕЙІН"),
    "workflow_title": ("Understand the system before you size it.", "Изучите систему, прежде чем выбирать её размер.", "Жүйе өлшемін таңдаудан бұрын оны түсініңіз."),
    "input_title": ("Start with the village", "Начните с села", "Ауылдан бастаңыз"),
    "input_body": ("Choose a location and check a year of weather. Add an hourly demand file, monthly totals, or an explicit estimate.", "Выберите место и проверьте год погоды. Загрузите почасовой спрос, месячные итоги или задайте явную оценку.", "Орынды таңдап, бір жылдық ауа райын тексеріңіз. Сағаттық сұранысты, айлық қорытындыларды немесе айқын бағалауды енгізіңіз."),
    "model_title": ("Follow every hour", "Проследите каждый час", "Әр сағатты бақылаңыз"),
    "model_body": ("Model wind and solar generation, serve demand, charge the battery, and account for the remaining shortfall.", "Смоделируйте ветер и солнце, обеспечьте спрос, зарядите накопитель и учтите оставшийся дефицит.", "Жел мен күн генерациясын модельдеп, сұранысты өтеңіз, жинақтағышты зарядтаңыз және қалған тапшылықты есептеңіз."),
    "output_title": ("Compare the tradeoffs", "Сравните компромиссы", "Ымыраларды салыстырыңыз"),
    "output_body": ("See how equipment size and lifecycle cost change when you ask the system to serve more annual energy.", "Посмотрите, как меняются размер оборудования и стоимость жизненного цикла при повышении годового энергообеспечения.", "Жылдық энергияны қамту артқанда жабдық өлшемі мен өмірлік цикл құны қалай өзгеретінін қараңыз."),
    "main_case": ("MAIN VILLAGE CASE", "ГЛАВНЫЙ ПРИМЕР СЕЛА", "НЕГІЗГІ АУЫЛ МЫСАЛЫ"),
    "case_body": ("A local question, made concrete: what mix of wind, solar, and storage could serve a 500 MWh/year community demand scenario?", "Конкретный местный вопрос: какое сочетание ветра, солнца и накопителей обеспечит сценарий спроса сообщества в 500 МВт·ч/год?", "Нақты жергілікті сұрақ: жел, күн және жинақтаудың қандай үйлесімі қауымдастықтың жылына 500 МВт·сағ сұраныс сценарийін қамтамасыз етеді?"),
    "estimate": ("Illustrative demand estimate · 2025 ERA5 weather · Saved planning results", "Иллюстративная оценка спроса · Погода ERA5 за 2025 год · Сохранённые результаты", "Көрнекі сұраныс бағалауы · 2025 жылғы ERA5 ауа райы · Сақталған нәтижелер"),
    "choose": ("Compare the planning target", "Сравнить цель планирования", "Жоспарлау мақсатын салыстыру"),
    "target": ("{value} target", "Цель {value}", "{value} мақсаты"),
    "served": ("of modeled annual demand served", "моделируемого годового спроса обеспечено", "модельденген жылдық сұраныс қамтылды"),
    "shortfall": ("annual energy shortfall", "годовой дефицит энергии", "жылдық энергия тапшылығы"),
    "wind": ("Wind", "Ветер", "Жел"),
    "solar": ("Solar DC", "Солнце DC", "Күн DC"),
    "storage": ("Usable storage", "Полезная ёмкость", "Пайдалы сыйымдылық"),
    "cost": ("Lifecycle cost (NPC)", "Стоимость жизненного цикла (ЧДД)", "Өмірлік цикл құны (ТДҚ)"),
    "chart_title": ("What the model sees, hour by hour", "Что видит модель, час за часом", "Модель сағат сайын не көреді"),
    "chart_note": ("First 7 days of 2025 · UTC · Hourly energy (kWh)", "Первые 7 дней 2025 года · UTC · Почасовая энергия (кВт·ч)", "2025 жылдың алғашқы 7 күні · UTC · Сағаттық энергия (кВт·сағ)"),
    "demand": ("Demand", "Спрос", "Сұраныс"),
    "solar_chart": ("Solar", "Солнце", "Күн"),
    "battery_chart": ("Stored battery energy · First 7 days (kWh)", "Запас энергии в накопителе · Первые 7 дней (кВт·ч)", "Жинақтағыштағы энергия · Алғашқы 7 күн (кВт·сағ)"),
    "jan": ("Jan", "янв.", "қаң."),
    "comparison": ("What changes with the target?", "Что меняется с целью?", "Мақсатпен бірге не өзгереді?"),
    "target_label": ("Target", "Цель", "Мақсат"),
    "served_label": ("Energy served", "Энергия обеспечена", "Энергия қамтылды"),
    "tradeoff": ("A higher target serves more energy, with a larger and more expensive system. Both designs use the same illustrative demand and weather inputs.", "Более высокая цель обеспечивает больше энергии, но требует более крупной и дорогой системы. Оба проекта используют одинаковые иллюстративные данные спроса и погоды.", "Жоғары мақсат көбірек энергияны қамтиды, бірақ үлкенірек әрі қымбатырақ жүйені қажет етеді. Екі жоба да бірдей көрнекі сұраныс пен ауа райы деректерін қолданады."),
    "scope": ("Modeled annual energy service is not uptime or a field guarantee. These are planning scenarios, not measured village consumption or procurement quotes.", "Моделируемое годовое энергообеспечение — не время бесперебойной работы и не полевая гарантия. Это сценарии планирования, а не измеренное потребление села или коммерческие предложения.", "Модельденген жылдық энергияны қамту — үздіксіз жұмыс уақыты немесе далалық кепілдік емес. Бұл өлшенген ауыл тұтынуы немесе коммерциялық ұсыныс емес, жоспарлау сценарийлері."),
    "workspace": ("EXPLORE THE WORKSPACE", "ИЗУЧИТЕ РАБОЧУЮ ОБЛАСТЬ", "ЖҰМЫС АЙМАҒЫН ЗЕРТТЕҢІЗ"),
    "workspace_title": ("Turn the example into your own question.", "Превратите пример в свой собственный вопрос.", "Мысалды өз сұрағыңызға айналдырыңыз."),
    "credit": ("Photos", "Фото", "Фотосуреттер"),
}


def _t(key: str, **values: object) -> str:
    return escape(COPY[key][("en", "ru", "kk").index(current_language())].format(**values))


@lru_cache(maxsize=4)
def _image(name: str) -> str:
    data = (Path(__file__).with_name("assets") / "landing" / name).read_bytes()
    return "data:image/jpeg;base64," + b64encode(data).decode("ascii")


@lru_cache(maxsize=2)
def _dispatch(target: float) -> pd.DataFrame:
    result = latest_result(FEATURED_SITE_ID, target)
    return pd.read_csv(project_root() / Path(result["_path"]).parent / "dispatch.csv")


def _energy_chart(target: float) -> str:
    frame = _dispatch(target).head(168)
    columns = (("demand_kwh", "#b98223", "demand"), ("wind_generation_kwh", "#4c8eaa", "wind"), ("pv_generation_kwh", "#0d7664", "solar_chart"))
    maximum = max(1.0, float(frame[[col for col, _, _ in columns]].max().max()))
    grid = "".join(f'<path d="M42 {y}H710" stroke="#dce4dc"/><text x="35" y="{y+4}" text-anchor="end">{maximum*(180-y)/160:.0f}</text>' for y in (20, 60, 100, 140, 180))
    lines = ""
    for column, color, key in columns:
        points = " ".join(f"{42 + index * 668 / (len(frame)-1):.1f},{180 - float(value) / maximum * 160:.1f}" for index, value in enumerate(frame[column]))
        lines += f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{points}"><title>{_t(key)}</title></polyline>'
    ticks = "".join(f'<text x="{42+index*24*668/(len(frame)-1):.1f}" y="205">{_t("jan")} {index+1}</text>' for index in range(7))
    return f'<svg class="sg-lp-chart" viewBox="0 0 730 220" role="img" aria-label="{_t("chart_title")}"><title>{_t("chart_title")}</title><g font-family="sans-serif" font-size="10" fill="#5b6e73">{grid}{lines}{ticks}</g></svg>'


def _battery_chart(target: float) -> str:
    series = _dispatch(target).head(168).battery_soc_end_kwh
    maximum = max(1.0, float(series.max()))
    points = " ".join(f"{index*400/(len(series)-1):.1f},{80-float(value)/maximum*70:.1f}" for index, value in enumerate(series))
    return f'<div class="sg-lp-battery"><p>{_t("battery_chart")} · 0–{maximum:,.0f}</p><svg viewBox="0 0 400 90" role="img" aria-label="{_t("battery_chart")}"><title>{_t("battery_chart")}</title><polygon points="0,80 {points} 400,80" fill="#7cc6aa22"/><polyline points="{points}" fill="none" stroke="#7cc6aa" stroke-width="2"/></svg><div><span>{_t("jan")} 1</span><span>{_t("jan")} 7</span></div></div>'


def render_landing(registry: SiteRegistry) -> None:
    site = registry.get_site(FEATURED_SITE_ID)
    lower, higher = latest_result(FEATURED_SITE_ID, .95), latest_result(FEATURED_SITE_ID, .99)
    stats = "".join(f'<div><strong>{value}</strong><span>{_t(key)}</span></div>' for value, key in ((len(registry.list_sites()), "villages"), (f"{len(_dispatch(.95)):,}", "hours"), ("95% / 99%", "targets"), ("3", "technologies")))
    workflow = "".join(f'<article><span class="sg-lp-step">0{index}</span><h3>{_t(prefix+"_title")}</h3><p>{_t(prefix+"_body")}</p></article>' for index, prefix in enumerate(("input", "model", "output"), 1))
    st.html(Path(__file__).with_name("assets") / "landing.css")
    st.markdown(
        '<section class="sg-lp"><div class="sg-lp-hero"><div class="sg-lp-copy">'
        f'<div class="sg-eyebrow">{_t("eyebrow")}</div><h1>{_t("title")}</h1><p>{_t("lead")}</p>'
        f'<div class="sg-lp-actions"><a class="sg-lp-primary" href="#planning-workspace" target="_self">{_t("start")} ↓</a><a href="#village-case" target="_self">{_t("see_case")} ↗</a></div></div>'
        f'<figure class="sg-lp-photos"><div class="sg-lp-photo-grid"><img src="{_image("korday-wind.jpg")}" alt="Korday wind farm near Moozbel, Kazakhstan"><img src="{_image("qonaev-solar.jpg")}" alt="Kapshagay solar power plant, Qonaev, Kazakhstan"><div class="sg-lp-photo-title">{_t("photo_title")}</div></div><figcaption>{_t("photo_note")}</figcaption></figure></div>'
        f'<div class="sg-lp-stats">{stats}</div><div class="sg-lp-section-heading"><div class="sg-eyebrow">{_t("workflow_kicker")}</div><h2>{_t("workflow_title")}</h2></div><div class="sg-lp-workflow">{workflow}</div>'
        f'<div id="village-case" class="sg-lp-case-heading"><div><div class="sg-eyebrow">{_t("main_case")}</div><h2>{escape(site.name)}</h2><span>{escape(site.region)} · {site.latitude:.4f}°N, {site.longitude:.4f}°E</span></div><p>{_t("case_body")}</p></div><p class="sg-lp-estimate">{_t("estimate")}</p></section>',
        unsafe_allow_html=True,
    )
    target = st.segmented_control(_t("choose"), (.95, .99), default=.95, key="landing_target", format_func=lambda value: _t("target", value=f"{value:.0%}")) or .95
    result = lower if target == .95 else higher
    design, metrics, economics = result["design"], result["metrics"], result["economics"]
    equipment = "".join(f'<div><span>{_t(key)}</span><strong>{value}</strong></div>' for key, value in (("wind", f'{design["wind_capacity_kw"]:,.0f} kW'), ("solar", f'{design["pv_dc_capacity_kw"]:,.1f} kW'), ("storage", f'{design["battery_usable_capacity_kwh"]/1000:.2f} MWh'), ("cost", f'${economics["net_present_cost_usd"]/1000000:.2f}M')))
    comparison = "".join(f'<tr><td>{row["reliability_target"]:.0%}</td><td>{row["metrics"]["served_fraction"]:.2%}</td><td>{row["design"]["battery_usable_capacity_kwh"]/1000:.2f} MWh</td><td>${row["economics"]["net_present_cost_usd"]/1000000:.2f}M</td></tr>' for row in (lower, higher))
    legend = "".join(f'<span><i style="background:{color}"></i>{_t(key)}</span>' for color, key in (("#b98223", "demand"), ("#4c8eaa", "wind"), ("#0d7664", "solar_chart")))
    st.markdown(
        '<section class="sg-lp"><div class="sg-lp-case-grid"><article class="sg-lp-result">'
        f'<div class="sg-lp-served">{metrics["served_fraction"]:.2%}</div><p>{_t("served")}</p><div class="sg-lp-energy-bar"><span style="width:{metrics["served_fraction"]*100:.3f}%"></span></div><div class="sg-lp-shortfall">{metrics["lpsp"]:.2%} {_t("shortfall")}</div><div class="sg-lp-equipment">{equipment}</div>{_battery_chart(target)}</article>'
        f'<article class="sg-lp-evidence"><h3>{_t("chart_title")}</h3><p class="sg-lp-chart-note">{_t("chart_note")}</p>{_energy_chart(target)}<div class="sg-lp-legend">{legend}</div><h3>{_t("comparison")}</h3><div class="sg-lp-table"><table><thead><tr><th>{_t("target_label")}</th><th>{_t("served_label")}</th><th>{_t("storage")}</th><th>NPC</th></tr></thead><tbody>{comparison}</tbody></table></div><p class="sg-lp-chart-note">{_t("tradeoff")}</p></article></div>'
        f'<p class="sg-lp-scope">{_t("scope")}</p><p class="sg-lp-credits">{_t("credit")}: <a href="https://commons.wikimedia.org/wiki/File:Korday_wind_farm_near_Moozbel_village,_Kazakhstan.jpg" target="_blank" rel="noopener noreferrer">Korday wind farm · МаратД</a> / <a href="https://commons.wikimedia.org/wiki/File:Конаев,_СЭС_сверху.jpg" target="_blank" rel="noopener noreferrer">Qonaev solar plant · Nikolai Bulykin</a> · <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noopener noreferrer">CC BY-SA 4.0</a></p>'
        f'<div id="planning-workspace" class="sg-lp-workspace"><div class="sg-eyebrow">{_t("workspace")}</div><h2>{_t("workspace_title")}</h2></div></section>',
        unsafe_allow_html=True,
    )
