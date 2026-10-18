from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest

from captura_ui import PreviewAgent, PreviewCoordinator, _play_agent
from core.agent_selection import WordPos
from core.agent_state import AgentState
from ui.agent_view import LINE_SEPARATOR


def _window(qapp):
    from coordinator_config import ClaudeSettings
    from ui._00_ui_main import MainWindow, load_fonts

    coordinator = PreviewCoordinator()
    agent = PreviewAgent(coordinator, ClaudeSettings())
    window = MainWindow(coordinator, load_fonts(), "light", agent=agent)
    window.show_module("agent")
    _play_agent(coordinator, agent, "sin_seleccion")
    window.show()
    qapp.processEvents()
    return window, agent


def _point_of(browser, phrase: int, word: str) -> QPoint:
    """El centro de `word` dentro del párrafo de la frase `phrase`, en el área visible."""
    block = browser.document().begin()
    while block.isValid() and block.userState() != phrase:
        block = block.next()
    text = block.text()
    start = text.index(LINE_SEPARATOR) + 1 + text.split(LINE_SEPARATOR, 1)[1].index(word)
    cursor = QTextCursor(block)
    cursor.setPosition(block.position() + start + len(word) // 2)
    return browser.cursorRect(cursor).center()


def test_left_click_marks_the_clicked_word_and_right_click_sends(qapp):
    window, agent = _window(qapp)
    view = window.agent_page.transcript
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=_point_of(view, 1, "plan"))
    assert agent.logic.state is AgentState.START_MARKED
    assert agent.start_mark == WordPos(1, 4)
    QTest.mouseClick(view.viewport(), Qt.MouseButton.RightButton, pos=_point_of(view, 2, "factura"))
    assert agent.logic.state is AgentState.SENDING
    assert agent.turns[0].selection.text().endswith("y todavía no me llega la factura")
    agent.answer("Con gusto.")
    assert agent.logic.state is AgentState.ANSWERED
    assert "Con gusto." in window.agent_page.turns_view.toPlainText()
    window.close()


def test_escape_cancels_a_marked_start(qapp):
    window, agent = _window(qapp)
    view = window.agent_page.transcript
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=_point_of(view, 0, "tardes"))
    QTest.keyClick(view, Qt.Key.Key_Escape)
    assert agent.logic.state is AgentState.IDLE
    window.close()


def test_modules_share_the_live_session(qapp):
    window, _agent = _window(qapp)
    assert window.coordinator.logic.can_stop
    window.show_module("live")
    assert window.current_module == "live"
    window.show_module("config")
    assert window.coordinator.logic.can_stop
    assert window.agent_page.run_button.text() == "Detener"
    window.close()
