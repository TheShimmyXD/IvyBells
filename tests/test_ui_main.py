from __future__ import annotations

from captura_ui import PreviewCoordinator


def test_theme_button_saves_the_new_theme(qapp):
    from ui._00_ui_main import MainWindow, load_fonts

    saved = []
    window = MainWindow(PreviewCoordinator(), load_fonts(), "dark", lambda *kv: saved.append(kv))
    window.theme_button.click()
    window.theme_button.click()
    assert saved == [("theme", "light"), ("theme", "dark")]
    window.close()


def test_saved_preferences_are_applied_and_changes_remembered(qapp):
    from ui._00_ui_main import MainWindow, load_fonts

    saved = []
    prefs = {"live_model": "small", "speaker": "tu", "module": "agent", "devices": {}}
    window = MainWindow(
        PreviewCoordinator(), load_fonts(), "light", lambda *kv: saved.append(kv), prefs=prefs
    )
    assert window.live_page.model_selector.current == "small"
    assert window.agent.speaker == "tu"
    assert window.current_module == "agent"
    assert saved == []  # aplicar las guardadas no las vuelve a escribir
    window.live_page.model_selector.buttons["medium"].click()
    window.agent_page.speaker_selector.buttons["ellos"].click()
    window.sidebar.buttons["config"].click()
    assert saved == [("live_model", "medium"), ("speaker", "ellos"), ("module", "config")]
    window.close()
