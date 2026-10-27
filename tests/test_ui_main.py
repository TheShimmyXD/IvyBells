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


def test_chat_panel_replaces_the_agent_column_and_is_remembered(qapp):
    from ui._00_ui_main import MainWindow, load_fonts

    saved = []
    prefs = {"module": "agent", "agent_panel": "chat"}
    window = MainWindow(
        PreviewCoordinator(), load_fonts(), "light", lambda *kv: saved.append(kv), prefs=prefs
    )
    page = window.agent_page
    assert page.panel == "chat" and page.right.currentWidget() is page.chat_panel
    assert saved == []
    page.panel_selector.buttons["agent"].click()
    assert page.panel == "agent"
    page.chat_panel.model_selector.buttons["opus"].click()
    assert saved == [("agent_panel", "agent")]  # el modelo del chat lo guarda su coordinador
    assert window.chat.model == "opus"
    assert window.agent.settings.config.model == "sonnet"  # el agente no cambia
    window.close()
