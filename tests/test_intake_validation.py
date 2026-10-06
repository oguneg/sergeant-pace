"""The model fills in the intake numbers from free text, so the tool must never trust them."""
import threading

import pytest

import agent
import tools
from conftest import onboard


@pytest.mark.parametrize("field,value", [
    ("age", -5), ("age", 9), ("age", 150), ("weight_kg", 1e9), ("weight_kg", 10), ("height_cm", 0), ("height_cm", 400),
    ("body_fat_pct", 0), ("body_fat_pct", 99), ("longest_run_km", -1), ("longest_run_km", 500),
    ("pace_min_per_km", 1), ("pace_min_per_km", 50), ("age", float("nan")), ("weight_kg", float("inf")),
    ("age", "thirty"), ("age", True),
])
def test_impossible_intake_values_are_rejected_and_nothing_is_saved(field, value):
    result = onboard(**{field: value})
    assert "error" in result
    assert tools.load_state() == {}


def test_boundary_intake_values_are_accepted():
    assert "error" not in onboard(age=10, weight_kg=30, height_cm=100, body_fat_pct=3, longest_run_km=0, pace_min_per_km=0)
    tools.reset_state()
    assert "error" not in onboard(age=100, weight_kg=300, height_cm=230, body_fat_pct=70, longest_run_km=100, pace_min_per_km=20)


def test_state_file_survives_a_crash_mid_write(monkeypatch):
    """Writes go to a temp file and are swapped in, so a failure while writing cannot corrupt the saved recruit."""
    onboard()
    before = tools.load_state()
    monkeypatch.setattr(tools.os, "replace", lambda *a: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError):
        tools.save_state({**before, "easy_pace": 1.0})
    assert tools.load_state() == before


def test_tool_trace_is_per_thread_so_visitors_never_see_each_others_calls():
    traced = agent.traced(tools.get_status)
    t = threading.Thread(target=traced)
    t.start()
    t.join()
    assert agent._trace() == []          # the other thread's call is not in this thread's trace
    traced()
    assert [c["tool"] for c in agent._trace()] == ["get_status"]
