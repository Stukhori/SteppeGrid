"""Small, explicit Russian/Kazakh localization layer for the Streamlit UI."""

from __future__ import annotations

from string import Formatter
from typing import Final

import streamlit as st

DEFAULT_LANGUAGE: Final = "ru"
LANGUAGE_STATE_KEY: Final = "interface_language"
LANGUAGE_LABELS: Final = {"ru": "Русский", "kk": "Қазақша"}

TRANSLATIONS: dict[str, dict[str, str]] = {
    "language": {"ru": "Язык", "kk": "Тіл"},
    "Explore": {"ru": "Обзор", "kk": "Шолу"},
    "Sites": {"ru": "Сёла", "kk": "Ауылдар"},
    "Compare": {"ru": "Сравнение", "kk": "Салыстыру"},
    "Plan": {"ru": "Планирование", "kk": "Жоспарлау"},
    "Overview": {"ru": "Обзор", "kk": "Шолу"},
    "Demand & Weather": {"ru": "Спрос и погода", "kk": "Сұраныс пен ауа райы"},
    "Renewable Generation": {"ru": "Возобновляемая генерация", "kk": "Жаңартылатын генерация"},
    "System Design": {"ru": "Конфигурация системы", "kk": "Жүйе конфигурациясы"},
    "Reliability": {"ru": "Надёжность", "kk": "Сенімділік"},
    "Economics": {"ru": "Экономика", "kk": "Экономика"},
    "Sensitivity": {"ru": "Чувствительность", "kk": "Сезімталдық"},
    "How SteppeGrid Works": {"ru": "Как работает SteppeGrid", "kk": "SteppeGrid қалай жұмыс істейді"},
    "Research pages": {"ru": "Исследовательские разделы", "kk": "Зерттеу бөлімдері"},
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


def placeholders(text: str) -> set[str]:
    """Expose format placeholders for catalog validation tests."""
    return {name for _, name, _, _ in Formatter().parse(text) if name}
