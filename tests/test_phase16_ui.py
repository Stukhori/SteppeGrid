from pathlib import Path

from streamlit.testing.v1 import AppTest
from steppegrid.app.i18n import translate


def test_sites_page_uses_dynamic_registry_and_exposes_onboarding():
    app = AppTest.from_file(Path(__file__).parents[1] / "app.py").run(timeout=90)
    next(control for control in app.segmented_control if control.label == translate("Primary navigation", "ru")).set_value("Sites").run(timeout=90)
    assert app.session_state["app_mode"] == "Sites"
    assert not app.exception
    assert any(box.label == "Изучить село" for box in app.selectbox)
    assert any(button.label == "Экспортировать JSON площадки" for button in app.download_button)
    assert any(tab.label == "Добавить площадку" for tab in app.tabs)
    assert any(field.label == "Идентификатор площадки" for field in app.text_input)
    assert any(button.label == "Проверить и сохранить" for button in app.button)


def test_builtin_site_has_no_delete_action_but_custom_temporary_planning_remains():
    app = AppTest.from_file(Path(__file__).parents[1] / "app.py").run(timeout=90)
    next(control for control in app.segmented_control if control.label == translate("Primary navigation", "ru")).set_value("Sites").run(timeout=90)
    assert not any(button.label == "Remove user site" for button in app.button)
    next(control for control in app.segmented_control if control.label == translate("Primary navigation", "ru")).set_value("Plan a System").run(timeout=90)
    site = next(box for box in app.selectbox if box.label == "Шаблон площадки")
    assert "Пользовательские координаты" in site.options
    for expected in (
        "Shamshi Kaldayakova", "Katon-Karagay", "Kegen", "Shayan", "Sai-Otes", "Togyzkuduk"
    ):
        assert expected in site.options
    assert not app.exception
