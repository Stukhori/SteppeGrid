import ast
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from steppegrid.app.english_catalog import ENGLISH_INLINE
from steppegrid.app.i18n import DEFAULT_LANGUAGE, LANGUAGE_LABELS, TRANSLATIONS, placeholders, translate


def test_language_catalog_is_complete_and_placeholder_safe():
    assert DEFAULT_LANGUAGE == "en"
    assert LANGUAGE_LABELS == {"en": "English", "ru": "Русский", "kk": "Қазақша"}
    for key, variants in TRANSLATIONS.items():
        assert set(variants) == set(LANGUAGE_LABELS), key
        assert all(value.strip() for value in variants.values()), key
        assert placeholders(variants["en"]) == placeholders(variants["ru"]) == placeholders(variants["kk"]), key


def test_inline_catalog_covers_static_copy_and_preserves_placeholders():
    root = Path(__file__).parents[1]
    for path in (root / "app.py", *sorted((root / "steppegrid/app").glob("*.py"))):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "loc"
                and len(node.args) >= 2
                and all(isinstance(arg, ast.Constant) and isinstance(arg.value, str) for arg in node.args[:2])
            ):
                continue
            russian, kazakh = node.args[0].value, node.args[1].value
            assert russian in ENGLISH_INLINE, f"missing English copy for {russian!r}"
            assert placeholders(ENGLISH_INLINE[russian]) == placeholders(russian) == placeholders(kazakh)


def test_translation_is_explicit_and_strict():
    assert translate("Sites", "ru") == "Сёла"
    assert translate("Sites", "kk") == "Ауылдар"
    assert translate("Sites", "en") == "Sites"
    assert translate("Plan a System", "ru") == "Спроектировать систему"
    assert translate("How SteppeGrid Works", "kk") == "SteppeGrid қалай жұмыс істейді"
    with pytest.raises(KeyError, match="missing kk interface translation"):
        translate("not registered", "kk")
    with pytest.raises(ValueError, match="unsupported interface language"):
        translate("Sites", "de")


@pytest.mark.parametrize("language", ["ru", "kk"])
def test_global_switch_changes_navigation(language):
    app = AppTest.from_file(Path(__file__).parents[1] / "app.py").run(timeout=90)
    switch = next(control for control in app.segmented_control if control.label == "Language / Язык / Тіл")
    assert switch.value == "en"
    switch.set_value(language).run(timeout=90)

    navigation = next(
        control for control in app.segmented_control
        if control.label == translate("Primary navigation", language)
    )
    assert navigation.options == [
        translate("Overview", language),
        translate("Sites", language),
        translate("Plan a System", language),
        translate("Compare", language),
        translate("Research", language),
    ]
    assert app.session_state["interface_language"] == language
    assert not app.exception
