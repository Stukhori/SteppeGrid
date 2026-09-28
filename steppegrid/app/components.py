"""Reusable Streamlit presentation components for the analytical UI."""

from __future__ import annotations

from html import escape
from typing import Iterable, Mapping

import pandas as pd
import streamlit as st

from steppegrid.app.formatting import energy, money, power
from steppegrid.app.i18n import loc, tr

GLOSSARY = {
    "served_energy": ("Доля обеспеченного годового спроса на электроэнергию. Это не процент часов непрерывной работы.", "Қамтылған жылдық электр сұранысының үлесі. Бұл үздіксіз жұмыс істеген сағаттардың пайызы емес."),
    "lpsp": ("Энергетическая вероятность потери питания: недоотпущенная годовая энергия, делённая на годовой спрос.", "Энергия бойынша қуат тапшылығы ықтималдығы: қамтылмаған жылдық энергияның жылдық сұранысқа қатынасы."),
    "lolh": ("Часы потери нагрузки: часы с любым смоделированным дефицитом электроэнергии.", "Жүктеме жоғалған сағаттар: модельде электр энергиясы жетіспеген кез келген сағат."),
    "npc": ("Чистая приведённая стоимость: дисконтированные затраты жизненного цикла при фиксированных экономических предпосылках.", "Таза келтірілген құн: бекітілген экономикалық болжамдардағы дисконтталған өмірлік цикл шығыны."),
    "eac": ("Эквивалентная годовая стоимость: годовой эквивалент чистой приведённой стоимости.", "Балама жылдық құн: таза келтірілген құнның жылдық баламасы."),
    "curtailment": ("Доступная возобновляемая энергия, не использованная нагрузкой и не принятая накопителем.", "Жүктеме пайдаланбаған және жинақтау жүйесі қабылдамаған қолжетімді жаңартылатын энергия."),
    "capacity_factor": ("Годовая энергия, делённая на номинальную мощность и число часов в году.", "Жылдық энергияның номиналды қуат пен жылдағы сағат санына қатынасы."),
    "poa": ("Солнечное излучение в плоскости смоделированной наклонной поверхности ФЭМ.", "Модельденген көлбеу ФЭМ бетіне түсетін жазықтықтағы күн сәулесі."),
    "binding_profile": ("Восстановленный профиль нагрузки с наименьшей долей обслуженной энергии для выбранного устойчивого проекта.", "Таңдалған тұрақты жоба үшін қамтылған энергия үлесі ең төмен қалпына келтірілген жүктеме профилі."),
}


def app_header() -> None:
    st.markdown(
        '<header class="sg-appbar"><div class="sg-appbar__brand"><span class="sg-appbar__mark">SG</span>'
        f'<span><strong>SteppeGrid</strong><small>{escape(tr("Village microgrid planning"))}</small></span></div>'
        f'<div class="sg-appbar__context"><span>{escape(tr("Kazakhstan"))}</span><a href="https://github.com/Stukhori/SteppeGrid" '
        f'target="_blank" rel="noopener noreferrer">{escape(tr("Project methods"))}</a></div></header>',
        unsafe_allow_html=True,
    )


def overview_intro() -> None:
    st.markdown(
        f'<section class="sg-overview-intro"><div class="sg-eyebrow">{escape(loc("Энергопланирование сёл Казахстана", "Қазақстан ауылдарын энергиямен жоспарлау"))}</div>'
        f'<h1>{escape(loc("Спроектируйте устойчивую сельскую микросеть", "Тұрақты ауылдық микрожеліні жобалаңыз"))}</h1><p>{escape(loc("Изучите, как почасовой спрос и местная погода определяют ветер, солнце, накопители, надёжность и стоимость жизненного цикла.", "Сағаттық сұраныс пен жергілікті ауа райының желге, күнге, жинақтау жүйесіне, сенімділікке және өмірлік цикл құнына әсерін зерттеңіз."))}</p></section>',
        unsafe_allow_html=True,
    )


def microgrid_schematic() -> None:
    aria = loc("Потоки энергии от ветра и солнца через аккумулятор к электрической нагрузке села", "Жел мен күн энергиясының аккумулятор арқылы ауылдың электр жүктемесіне ағыны")
    title = loc("Схема энергетических потоков сельской микросети", "Ауылдық микрожелінің энергия ағыны сызбасы")
    st.markdown(
        f'<figure class="sg-schematic" aria-label="{escape(aria)}">'
        f'<svg viewBox="0 0 680 280" role="img"><title>{escape(title)}</title>'
        '<path class="sg-grid" d="M30 224H650M52 248H628"/><path class="sg-flowline" d="M157 171H284M392 171H522"/>'
        '<g class="sg-wind"><path d="M130 94v110M112 204h36"/><circle cx="130" cy="88" r="7"/>'
        '<path d="M130 80l-8-52M136 90l48-24M126 94l-38 37"/></g>'
        '<g class="sg-sun"><circle cx="236" cy="48" r="19"/><path d="M236 15v-9M236 90v-9M203 48h-9M278 48h-9M213 25l-7-7M266 78l-7-7M259 25l7-7M206 78l7-7"/></g>'
        '<g class="sg-solar"><path d="M196 132h82l16 55h-114zM207 132l-8 55M234 132v55M261 132l8 55M188 158h98M218 187l-8 18M270 187l8 18"/></g>'
        '<g class="sg-battery"><rect x="304" y="124" width="88" height="96" rx="7"/><path d="M337 111h22v13M326 151h44M326 174h44M326 197h26"/></g>'
        '<g class="sg-village"><path d="M500 159l46-38 46 38v62h-92zM516 221v-35h24v35M566 221v-29h15v29M612 221v-48h22v48M607 173h32"/></g>'
        f'<text x="92" y="242">{escape(loc("Ветер", "Жел"))}</text><text x="205" y="242">{escape(loc("Солнце", "Күн"))}</text><text x="310" y="242">{escape(loc("Накопитель", "Жинақтау"))}</text><text x="512" y="242">{escape(loc("Нагрузка села", "Ауыл жүктемесі"))}</text>'
        f'</svg><figcaption>{escape(loc("Почасовая генерация → диспетчеризация накопителя → нагрузка села", "Сағаттық генерация → жинақтау жүйесін диспетчерлеу → ауыл жүктемесі"))}</figcaption></figure>',
        unsafe_allow_html=True,
    )


def resource_strip() -> None:
    items = (
        ("7", loc("сёл", "ауыл")),
        ("8,760", loc("часовых шагов", "сағаттық қадам")),
        (loc("Ветер + солнце", "Жел + күн"), loc("модели ресурсов", "ресурс модельдері")),
        ("95% / 99%", loc("цели планирования", "жоспарлау мақсаттары")),
    )
    rendered = "".join(f'<div><strong>{escape(value)}</strong><span>{escape(label)}</span></div>' for value, label in items)
    st.markdown(f'<div class="sg-resource-strip">{rendered}</div>', unsafe_allow_html=True)


def page_header(eyebrow: str, title: str, lead: str, badges: Iterable[tuple[str, str]] = ()) -> None:
    rendered = "".join(f'<span class="sg-badge sg-badge--{escape(tone)}">{escape(label)}</span>' for label, tone in badges)
    badge_row = f'<div class="sg-badges">{rendered}</div>' if rendered else ""
    st.markdown(f'<header class="sg-pagehead"><div class="sg-eyebrow">{escape(eyebrow)}</div><h1>{escape(title)}</h1><p>{escape(lead)}</p>{badge_row}</header>', unsafe_allow_html=True)


def section_header(title: str, description: str = "") -> None:
    copy = f"<p>{escape(description)}</p>" if description else ""
    st.markdown(f'<div class="sg-section"><h2>{escape(title)}</h2>{copy}</div>', unsafe_allow_html=True)


def callout(title: str, body: str, tone: str = "info") -> None:
    modifier = "" if tone == "info" else f" sg-callout--{tone}"
    st.markdown(f'<div class="sg-callout{modifier}"><strong>{escape(title)}</strong>{escape(body)}</div>', unsafe_allow_html=True)


def metric(label: str, value: str, *, help_key: str | None = None, delta: str | None = None) -> None:
    help_text = loc(*GLOSSARY[help_key]) if help_key else None
    st.metric(label, value, delta=delta, help=help_text)


def equipment_card(kicker: str, title: str, value: str, stats: Mapping[str, str]) -> None:
    items = "".join(f'<div class="sg-stat"><span>{escape(label)}</span><b>{escape(item)}</b></div>' for label, item in stats.items())
    st.markdown(f'<div class="sg-card"><div class="sg-card__kicker">{escape(kicker)}</div><div class="sg-card__title">{escape(title)}</div><div class="sg-card__value">{escape(value)}</div><div class="sg-stat-grid">{items}</div></div>', unsafe_allow_html=True)


def design_card(kind: str, headline: str, capacity: str, detail: str) -> None:
    st.markdown(f'<div class="sg-card"><div class="sg-card__kicker">{escape(kind)}</div><div class="sg-card__title">{escape(headline)}</div><div class="sg-card__value">{escape(capacity)}</div><div class="sg-card__meta">{escape(detail)}</div></div>', unsafe_allow_html=True)


def workflow(steps: Iterable[str]) -> None:
    nodes = "".join(
        f'<div class="sg-workflow__step"><b>{index:02d}</b><span>{escape(step)}</span></div>'
        for index, step in enumerate(steps, start=1)
    )
    st.markdown(f'<div class="sg-workflow">{nodes}</div>', unsafe_allow_html=True)


def site_status(name: str, status: str, details: Iterable[str], *, pending: bool = False) -> None:
    tone, modifier = ("warning", " sg-site--pending") if pending else ("success", "")
    copy = "".join(f"<p>{escape(detail)}</p>" for detail in details)
    st.markdown(f'<div class="sg-site{modifier}"><span class="sg-badge sg-badge--{tone}">{escape(status)}</span><h3>{escape(name)}</h3>{copy}</div>', unsafe_allow_html=True)


def energy_flow(wind_kwh: float, pv_kwh: float, served_kwh: float, curtailed_kwh: float, unmet_kwh: float) -> None:
    st.markdown(
        '<div class="sg-flow">'
        f'<div class="sg-flow__node"><b>{escape(loc("Ветер + солнце", "Жел + күн"))}</b><span>{escape(energy(wind_kwh + pv_kwh))} {escape(loc("возобновляемой генерации", "жаңартылатын генерация"))}</span></div>'
        '<div class="sg-flow__arrow">→</div>'
        f'<div class="sg-flow__node"><b>{escape(loc("Почасовая диспетчеризация + накопитель", "Сағаттық диспетчерлеу + жинақтау"))}</b><span>{escape(energy(served_kwh))} {escape(loc("обслуженной нагрузки", "қамтылған жүктеме"))}</span></div>'
        '<div class="sg-flow__arrow">→</div>'
        f'<div class="sg-flow__node"><b>{escape(loc("Годовой баланс", "Жылдық теңгерім"))}</b><span>{escape(energy(curtailed_kwh))} {escape(loc("ограничено", "шектелді"))} · {escape(energy(unmet_kwh))} {escape(loc("дефицит", "тапшылық"))}</span></div>'
        '</div>',
        unsafe_allow_html=True,
    )


def comparison_table(rows: list[dict]) -> None:
    frame = pd.DataFrame(rows).rename(columns={"Measure": loc("Показатель", "Көрсеткіш"), "Change": loc("Изменение", "Өзгеріс")})
    st.dataframe(frame, hide_index=True, width="stretch")


def audit_status(checks: int, blockers: int, warnings: int, tests: int) -> None:
    cols = st.columns(4)
    cols[0].metric(loc("Проверки валидации", "Валидация тексерістері"), checks); cols[1].metric(loc("Блокирующие ошибки", "Бұғаттаушы қателер"), blockers)
    cols[2].metric(loc("Предупреждения области", "Қамту ескертулері"), warnings); cols[3].metric(loc("Регрессионные тесты", "Регрессиялық тесттер"), tests)


def limitations(groups: Mapping[str, Iterable[str]]) -> None:
    for title, items in groups.items():
        with st.expander(title, expanded=False):
            for item in items: st.markdown(f"- {item}")


def design_comparison_rows(lower: dict, higher: dict) -> list[dict]:
    def change(a: float, b: float) -> str: return f"{100 * (b / a - 1):+.1f}%" if a else "—"
    return [
        {"Measure": loc("Мощность ветра", "Жел қуаты"), "95%": power(lower["installed_wind_kw"]), "99%": power(higher["installed_wind_kw"]), "Change": change(lower["installed_wind_kw"], higher["installed_wind_kw"])},
        {"Measure": loc("Мощность ФЭМ AC", "ФЭМ AC қуаты"), "95%": power(lower["installed_pv_ac_kw"]), "99%": power(higher["installed_pv_ac_kw"]), "Change": change(lower["installed_pv_ac_kw"], higher["installed_pv_ac_kw"])},
        {"Measure": loc("Полезная ёмкость", "Пайдалы сыйымдылық"), "95%": energy(lower["installed_usable_battery_kwh"]), "99%": energy(higher["installed_usable_battery_kwh"]), "Change": change(lower["installed_usable_battery_kwh"], higher["installed_usable_battery_kwh"])},
        {"Measure": loc("Чистая приведённая стоимость", "Таза келтірілген құн"), "95%": money(lower["net_present_cost_usd"]), "99%": money(higher["net_present_cost_usd"]), "Change": change(lower["net_present_cost_usd"], higher["net_present_cost_usd"])},
        {"Measure": loc("Часы потери нагрузки", "Жүктеме жоғалған сағаттар"), "95%": f"{lower['loss_of_load_hours']} h", "99%": f"{higher['loss_of_load_hours']} h", "Change": change(lower["loss_of_load_hours"], higher["loss_of_load_hours"])},
        {"Measure": loc("Ограничение генерации", "Генерацияны шектеу"), "95%": energy(lower["curtailment_kwh"]), "99%": energy(higher["curtailment_kwh"]), "Change": change(lower["curtailment_kwh"], higher["curtailment_kwh"])},
    ]
