"""Small, explicit Russian/Kazakh localization layer for the Streamlit UI."""

from __future__ import annotations

from string import Formatter
from typing import Final

import streamlit as st

from steppegrid.app.english_catalog import ENGLISH_INLINE

DEFAULT_LANGUAGE: Final = "en"
LANGUAGE_STATE_KEY: Final = "interface_language"
LANGUAGE_LABELS: Final = {"en": "English", "ru": "Русский", "kk": "Қазақша"}

TRANSLATIONS: dict[str, dict[str, str]] = {
    "language": {"en": "Language", "ru": "Язык", "kk": "Тіл"},
    "Explore": {"en": "Explore", "ru": "Обзор", "kk": "Шолу"},
    "Sites": {"en": "Sites", "ru": "Сёла", "kk": "Ауылдар"},
    "Compare": {"en": "Compare", "ru": "Сравнение", "kk": "Салыстыру"},
    "Plan": {"en": "Plan", "ru": "Планирование", "kk": "Жоспарлау"},
    "Overview": {"en": "Overview", "ru": "Обзор", "kk": "Шолу"},
    "Demand & Weather": {"en": "Demand & Weather", "ru": "Спрос и погода", "kk": "Сұраныс пен ауа райы"},
    "Renewable Generation": {"en": "Renewable Generation", "ru": "Возобновляемая генерация", "kk": "Жаңартылатын генерация"},
    "System Design": {"en": "System Design", "ru": "Конфигурация системы", "kk": "Жүйе конфигурациясы"},
    "Reliability": {"en": "Reliability", "ru": "Надёжность", "kk": "Сенімділік"},
    "Economics": {"en": "Economics", "ru": "Экономика", "kk": "Экономика"},
    "Sensitivity": {"en": "Sensitivity", "ru": "Чувствительность", "kk": "Сезімталдық"},
    "How SteppeGrid Works": {"en": "How SteppeGrid Works", "ru": "Как работает SteppeGrid", "kk": "SteppeGrid қалай жұмыс істейді"},
    "Research pages": {"en": "Research pages", "ru": "Исследовательские разделы", "kk": "Зерттеу бөлімдері"},
    "Plan a System": {"en": "Plan a System", "ru": "Спроектировать систему", "kk": "Жүйені жобалау"},
    "Research": {"en": "Research", "ru": "Исследование", "kk": "Зерттеу"},
    "Primary navigation": {"en": "Primary navigation", "ru": "Основная навигация", "kk": "Негізгі навигация"},
    "Research page": {"en": "Research page", "ru": "Раздел исследования", "kk": "Зерттеу бөлімі"},
    "Methodology & Provenance": {"en": "Methodology & Provenance", "ru": "Методология и происхождение данных", "kk": "Әдіснама және деректердің шығу тегі"},
    "Village microgrid planning": {"en": "Village microgrid planning", "ru": "Планирование сельских микросетей", "kk": "Ауылдық микрожелілерді жоспарлау"},
    "Kazakhstan": {"en": "Kazakhstan", "ru": "Казахстан", "kk": "Қазақстан"},
    "Project methods": {"en": "Project methods ↗", "ru": "Методы проекта ↗", "kk": "Жоба әдістері ↗"},
}


def current_language() -> str:
    """Return the active language, defaulting safely outside a Streamlit session."""
    try:
        value = st.session_state.get(LANGUAGE_STATE_KEY, DEFAULT_LANGUAGE)
    except Exception:
        return DEFAULT_LANGUAGE
    return value if value in LANGUAGE_LABELS else DEFAULT_LANGUAGE


def translate(key: str, language: str, **values: object) -> str:
    """Translate one catalog key and interpolate named values."""
    if language not in LANGUAGE_LABELS:
        raise ValueError(f"unsupported interface language: {language}")
    try:
        template = TRANSLATIONS[key][language]
    except KeyError as error:
        raise KeyError(f"missing {language} interface translation for {key!r}") from error
    return template.format(**values)


def tr(key: str, **values: object) -> str:
    """Translate with the language stored in the current Streamlit session."""
    return translate(key, current_language(), **values)


def loc(ru: str, kk: str, **values: object) -> str:
    """Select English, Russian, or Kazakh copy unique to one view."""
    language = current_language()
    if language == "en":
        try:
            template = ENGLISH_INLINE[ru]
        except KeyError as error:
            raise KeyError(f"missing en inline translation for {ru!r}") from error
    else:
        template = ru if language == "ru" else kk
    return template.format(**values)


def language_switch() -> str:
    """Render the global language control and persist its stable language code."""
    selected = st.segmented_control(
        "Language / Язык / Тіл",
        tuple(LANGUAGE_LABELS),
        default=current_language(),
        format_func=LANGUAGE_LABELS.__getitem__,
        key="_interface_language_switch",
    )
    language = selected or DEFAULT_LANGUAGE
    st.session_state[LANGUAGE_STATE_KEY] = language
    return language


def placeholders(text: str) -> set[str]:
    """Expose format placeholders for catalog validation tests."""
    return {name for _, name, _, _ in Formatter().parse(text) if name}
