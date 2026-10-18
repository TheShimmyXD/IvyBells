from __future__ import annotations

from core.agent_selection import WordPos
from core.agent_state import AgentLogic, AgentState


def test_full_turn():
    logic = AgentLogic()
    assert logic.status.startswith("Clic izquierdo")
    assert logic.mark_end(WordPos(0, 0)) is None  # sin inicio no envía
    assert logic.mark_start(WordPos(2, 1))
    assert logic.state is AgentState.START_MARKED
    assert logic.mark_end(WordPos(0, 4), "sonnet") == (WordPos(0, 4), WordPos(2, 1))
    assert logic.state is AgentState.SENDING
    assert logic.status == "Enviando a sonnet..."
    logic.answered()
    assert logic.state is AgentState.ANSWERED
    assert logic.answers == 1


def test_no_marks_while_sending():
    logic = AgentLogic()
    logic.mark_start(WordPos(0, 0))
    logic.mark_end(WordPos(0, 1))
    assert not logic.mark_start(WordPos(1, 0))
    assert not logic.reset()
    assert logic.state is AgentState.SENDING


def test_new_start_replaces_previous_start():
    logic = AgentLogic()
    logic.mark_start(WordPos(0, 0))
    logic.mark_start(WordPos(3, 2))
    assert logic.mark_end(WordPos(4, 0)) == (WordPos(3, 2), WordPos(4, 0))


def test_cancel_returns_to_rest_keeping_answers():
    logic = AgentLogic()
    logic.mark_start(WordPos(0, 0))
    assert logic.cancel()
    assert logic.state is AgentState.IDLE
    logic.mark_start(WordPos(0, 0))
    logic.mark_end(WordPos(0, 1))
    logic.answered()
    logic.mark_start(WordPos(1, 0))
    logic.cancel()
    assert logic.state is AgentState.ANSWERED
    assert not logic.cancel()


def test_cancel_while_sending():
    logic = AgentLogic()
    logic.mark_start(WordPos(0, 0))
    logic.mark_end(WordPos(0, 1))
    assert logic.cancel()
    assert logic.state is AgentState.IDLE


def test_fail_then_mark_again():
    logic = AgentLogic()
    logic.mark_start(WordPos(0, 0))
    logic.mark_end(WordPos(0, 1))
    logic.fail("tiempo agotado")
    assert logic.state is AgentState.ERROR
    assert logic.status == "Error: tiempo agotado"
    assert logic.mark_start(WordPos(1, 0))


def test_answered_and_fail_only_count_while_sending():
    logic = AgentLogic()
    logic.answered()
    logic.fail("x")
    assert logic.state is AgentState.IDLE
    assert logic.answers == 0


def test_reset_forgets_everything():
    logic = AgentLogic()
    logic.mark_start(WordPos(0, 0))
    logic.mark_end(WordPos(0, 1))
    logic.answered()
    assert logic.reset()
    assert logic.state is AgentState.IDLE
    assert logic.answers == 0
