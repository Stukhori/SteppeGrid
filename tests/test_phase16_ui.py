from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_sites_page_uses_dynamic_registry_and_exposes_onboarding():
    app = AppTest.from_file(Path(__file__).parents[1] / "app.py").run(timeout=90)
    next(button for button in app.button if button.label == "Sites").click().run(timeout=90)
    assert app.session_state["app_mode"] == "Sites"
    assert not app.exception
    assert any(box.label == "Inspect site" for box in app.selectbox)
    assert any(button.label == "Export site JSON" for button in app.download_button)
    assert any(tab.label == "Add new site" for tab in app.tabs)
    assert any(field.label == "Site ID" for field in app.text_input)
    assert any(button.label == "Validate and save site" for button in app.button)


def test_builtin_site_has_no_delete_action_but_custom_temporary_planning_remains():
    app = AppTest.from_file(Path(__file__).parents[1] / "app.py").run(timeout=90)
    next(button for button in app.button if button.label == "Sites").click().run(timeout=90)
    assert not any(button.label == "Remove user site" for button in app.button)
    next(button for button in app.button if button.label == "Plan").click().run(timeout=90)
    site = next(box for box in app.selectbox if box.label == "Site preset")
    assert "Custom coordinates" in site.options
    assert "Shamshi Kaldayakova" in site.options
    assert not app.exception
