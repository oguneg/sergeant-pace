"""The agent's tools have side effects, so a failed Gemini turn must not leave half a change behind.
These tests replace the model with a fake chat, so they need no API key and no network."""
import pytest

import agent
import tools
from conftest import onboard


class FakeChat:
    """Plays a script: each entry is either an exception to raise or a callable run as the 'tool calls' of that attempt."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def send_message(self, text):
        self.calls += 1
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        step()  # may mutate state, like a tool call would
        part = type("Part", (), {"text": "Move it, recruit."})()
        content = type("Content", (), {"parts": [part]})()
        return type("Resp", (), {"candidates": [type("Cand", (), {"content": content})()]})()

    def get_history(self):
        return ["history"]


def make_coach(chat, next_chats=()):
    coach = agent.Coach.__new__(agent.Coach)  # skip __init__, which needs an API key
    coach.model_idx = 0
    coach.chat = chat
    pending = list(next_chats)
    coach._make_chat = lambda history=None: pending.pop(0)
    return coach


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(agent.time, "sleep", lambda s: None)


def test_busy_error_rolls_back_the_half_finished_turn_then_retries():
    onboard()
    runs_before = len(tools.load_state()["history"])
    # attempt 1: a tool call lands, then the model call dies. Attempt 2 succeeds without touching state.
    coach = make_coach(FakeChat([_do_then_fail(lambda: tools.skip_run("half done"), RuntimeError("503 UNAVAILABLE")),
                                 lambda: None]))
    reply, _ = coach.send("[Run skipped] whatever")
    assert reply == "Move it, recruit."
    assert len(tools.load_state()["history"]) == runs_before   # the aborted skip was undone, not duplicated
    assert coach.chat.calls == 2


def _do_then_fail(side_effect, error):
    def step():
        side_effect()
        raise error
    return step


def test_quota_error_switches_model_and_keeps_history():
    onboard()
    first = FakeChat([_do_then_fail(lambda: tools.skip_run("x"), RuntimeError("429 RESOURCE_EXHAUSTED"))])
    second = FakeChat([lambda: None])
    coach = make_coach(first, [second])
    reply, _ = coach.send("hello")
    assert reply == "Move it, recruit."
    assert coach.model_idx == 1 and coach.chat is second
    assert tools.load_state()["history"] == []                   # the failed attempt's skip was rolled back


def test_unrecoverable_error_is_raised_and_state_restored():
    onboard()
    coach = make_coach(FakeChat([_do_then_fail(lambda: tools.skip_run("x"), ValueError("bad request"))]))
    with pytest.raises(ValueError):
        coach.send("hello")
    assert tools.load_state()["history"] == []


def test_rollback_with_no_recruit_yet_leaves_no_state_behind():
    coach = make_coach(FakeChat([_do_then_fail(lambda: onboard(), ValueError("boom"))]))
    with pytest.raises(ValueError):
        coach.send("[Intake form submitted] ...")
    assert tools.load_state() == {}


def test_running_out_of_models_raises_instead_of_looping():
    onboard()
    coach = make_coach(FakeChat([RuntimeError("429 RESOURCE_EXHAUSTED")]))
    coach.model_idx = len(agent.MODELS) - 1
    with pytest.raises(RuntimeError):
        coach.send("hello")


# ---------- a slow model is as bad as a broken one ----------

@pytest.mark.parametrize("error,kind", [
    (RuntimeError("429 RESOURCE_EXHAUSTED. quota"), "quota"), (RuntimeError("404 NOT_FOUND model gone"), "quota"),
    (TimeoutError("took too long"), "slow"), (RuntimeError("The read operation timed out"), "slow"), (RuntimeError("504 DEADLINE_EXCEEDED"), "slow"),
    (RuntimeError("503 UNAVAILABLE"), "busy"), (RuntimeError("500 INTERNAL"), "busy"),
    (ValueError("bad request"), "other"),
])
def test_upstream_errors_are_classified(error, kind):
    assert agent.kind_of(error) == kind


def test_a_timed_out_model_is_abandoned_for_the_next_one():
    onboard()
    first = FakeChat([_do_then_fail(lambda: tools.skip_run("x"), RuntimeError("The read operation timed out"))])
    second = FakeChat([lambda: None])
    coach = make_coach(first, [second])
    reply, _ = coach.send("hello")
    assert coach.model_idx == 1 and coach.chat is second and reply == "Move it, recruit."
    assert tools.load_state()["history"] == []          # the half-finished attempt was rolled back first


def test_a_turn_stops_at_its_time_budget_instead_of_walking_every_model(monkeypatch):
    onboard()
    clock = {"t": 1000.0}
    monkeypatch.setattr(agent.time, "monotonic", lambda: clock["t"])

    class Slow:
        def __init__(self):
            self.calls = 0

        def send_message(self, text):
            self.calls += 1
            clock["t"] += agent.REQUEST_TIMEOUT_S           # each attempt burns its full timeout
            raise TimeoutError("timed out")

        def get_history(self):
            return []

    chats = [Slow() for _ in range(6)]
    coach = make_coach(chats[0], chats[1:])
    with pytest.raises(TimeoutError):
        coach.send("hello")
    attempts = sum(c.calls for c in chats)
    assert attempts * agent.REQUEST_TIMEOUT_S <= agent.TURN_BUDGET_S + agent.REQUEST_TIMEOUT_S   # bounded, not all six models
    assert tools.load_state()["history"] == []
