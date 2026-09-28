import pytest
from pathlib import Path
from streamlit.testing.v1 import AppTest

from steppegrid.app.i18n import LANGUAGE_LABELS, TRANSLATIONS, placeholders, translate


def test_language_catalog_is_complete_and_placeholder_safe():
    assert LANGUAGE_LABELS == {"ru": "Русский", "kk": "Қазақша"}
    for key, variants in TRANSLATIONS.items():
        assert set(variants) == set(LANGUAGE_LABELS), key
        assert all(value.strip() for value in variants.values()), key
        assert placeholders(variants["ru"]) == placeholders(variants["kk"]), key


def test_translation_is_explicit_and_strict():
    assert translate("Sites", "ru") == "Сёла"
    assert translate("Sites", "kk") == "Ауылдар"
    assert translate("Plan a System", "ru") == "Спроектировать систему"
    assert translate("How SteppeGrid Works", "kk") == "SteppeGrid қалай жұмыс істейді"
    with pytest.raises(KeyError, match="missing kk interface translation"):
        translate("not registered", "kk")
    with pytest.raises(ValueError, match="unsupported interface language"):
        translate("Sites", "en")


def test_global_switch_changes_navigation_to_kazakh():
    app = AppTest.from_file(Path(__file__).parents[1] / "app.py").run(timeout=90)
    switch = next(control for control in app.segmented_control if control.label == "Язык / Тіл")
    switch.set_value("kk").run(timeout=90)

    navigation = next(
        control for control in app.segmented_control
        if control.label == translate("Primary navigation", "kk")
    )
    assert navigation.options == [
        translate("Overview", "kk"),
        translate("Sites", "kk"),
        translate("Plan a System", "kk"),
        translate("Compare", "kk"),
        translate("Research", "kk"),
    ]
    assert app.session_state["interface_language"] == "kk"
    assert not app.exception
