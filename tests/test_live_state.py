from __future__ import annotations

from core.live_state import CAPTURE_LOST, LiveLogic, LiveState


def test_normal_cycle():
    logic = LiveLogic()
    assert logic.start("large-v3-turbo")["ok"]
    assert logic.state is LiveState.LOADING
    assert "large-v3-turbo" in logic.status
    assert logic.loaded()["ok"]
    assert logic.status == "Escuchando"
    assert logic.stop()["ok"]
    assert logic.state is LiveState.STOPPING
    logic.finished()
    assert logic.state is LiveState.STOPPED
    assert not logic.is_busy


def test_cannot_start_twice():
    logic = LiveLogic()
    logic.start("small")
    assert not logic.start("small")["ok"]


def test_stop_while_loading_ends_stopped():
    logic = LiveLogic()
    logic.start("small")
    logic.stop()
    logic.finished()
    assert logic.state is LiveState.STOPPED


def test_capture_lost_while_listening_is_error():
    logic = LiveLogic()
    logic.start("small")
    logic.loaded()
    logic.finished()
    assert logic.state is LiveState.ERROR
    assert logic.message == CAPTURE_LOST


def test_failure_survives_finished_and_allows_restart():
    logic = LiveLogic()
    logic.start("small")
    logic.fail("sin GPU")
    logic.finished()
    assert logic.state is LiveState.ERROR
    assert logic.status == "Error: sin GPU"
    assert logic.can_start
    assert logic.start("small")["ok"]
    assert logic.message == ""
