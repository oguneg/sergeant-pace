"""Regression for a bug that only appears with two visitors at once: each conversation built its own Gemini client and overwrote a
shared global, so the first client was garbage collected and closed while its request was still running."""
import threading
import time
from types import SimpleNamespace

import pytest

import agent


class FakeClient:
    created = 0

    options = None

    def __init__(self, api_key=None, http_options=None):
        FakeClient.created += 1
        FakeClient.options = http_options
        self.chats = SimpleNamespace(create=lambda **kw: SimpleNamespace(kw=kw, get_history=lambda: []))


@pytest.fixture(autouse=True)
def fake_genai(monkeypatch):
    FakeClient.created = 0
    monkeypatch.setattr(agent.genai, "Client", FakeClient)
    monkeypatch.setattr(agent, "_client", None)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")


def test_every_conversation_shares_one_client():
    a, b, c = agent.Coach(), agent.Coach(), agent.Coach()
    assert FakeClient.created == 1
    assert agent.client() is agent.client()


def test_visitors_arriving_together_still_get_one_client():
    start = threading.Barrier(12)
    seen = []

    def arrive():
        start.wait()
        agent.Coach()
        seen.append(agent.client())

    threads = [threading.Thread(target=arrive) for _ in range(12)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert FakeClient.created == 1 and len({id(c) for c in seen}) == 1


def test_a_missing_key_is_a_clear_error_not_a_crash(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY")
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        agent.Coach()


def test_new_conversations_start_from_the_last_model_that_worked(monkeypatch):
    first = agent.Coach()
    assert first.model_idx == 0
    first._next_model()                      # quota ran out on model 0
    first._next_model()                      # ...and on model 1
    assert agent.Coach().model_idx == 2      # the next visitor does not retry them


def test_the_top_model_is_tried_again_after_an_hour(monkeypatch):
    agent.Coach()._next_model()
    assert agent.Coach().model_idx == 1
    later = agent.time.time() + agent.RETRY_TOP_AFTER + 1
    monkeypatch.setattr(agent.time, "time", lambda: later)
    assert agent.Coach().model_idx == 0


def test_the_client_fails_fast_instead_of_retrying_for_minutes():
    """The SDK default is 5 attempts with exponential backoff and no timeout, which stalled visitors for 70 to 144 seconds."""
    agent.client()
    opts = FakeClient.options
    assert opts.retry_options.attempts == 1
    assert opts.timeout == agent.REQUEST_TIMEOUT_S * 1000 and agent.REQUEST_TIMEOUT_S <= 30


# ---------- finding the fast model before a visitor has to ----------

def test_probing_skips_slow_models_and_remembers_the_first_fast_one(monkeypatch):
    answers = {"gemini-3.8-flash": False, "gemini-3.7-flash": False}          # throttled: would hold a visitor for a minute
    monkeypatch.setattr(agent, "_probe", lambda m: answers.get(m, True))
    assert agent.probe_models() == 2 and agent.MODELS[2] == "gemini-3.6-flash"
    assert agent.Coach().model_idx == 2                                         # the first visitor starts there, not at the top


def test_probing_reports_nothing_when_every_model_is_down(monkeypatch):
    monkeypatch.setattr(agent, "_probe", lambda m: False)
    assert agent.probe_models() is None


def test_a_recovered_top_model_is_picked_up_in_the_background(monkeypatch):
    state = {"top_ok": False}
    monkeypatch.setattr(agent, "_probe", lambda m: m != agent.MODELS[0] or state["top_ok"])
    agent.probe_models()
    assert agent.Coach().model_idx == 1
    state["top_ok"] = True
    agent.probe_models()
    assert agent.Coach().model_idx == 0


def test_the_background_loop_probes_then_waits_and_stops_on_request(monkeypatch):
    import threading
    calls = []
    monkeypatch.setattr(agent, "probe_models", lambda: calls.append(1))
    stop = threading.Event()
    t = threading.Thread(target=agent.maintain_models, args=(stop, 0.05))
    t.start()
    time.sleep(0.25)
    stop.set()
    t.join(2)
    assert not t.is_alive() and len(calls) >= 2                                  # at startup and again after the pause


def test_the_probe_cannot_stall_for_minutes():
    assert agent.PROBE_TIMEOUT_S <= 20 and agent.REPROBE_EVERY_S < agent.RETRY_TOP_AFTER


def test_no_deadline_is_shorter_than_the_api_allows():
    """Gemini answers 400 'deadline too short' below 10 s. An 8 s probe timeout once made every probe fail, and silently."""
    assert agent.MIN_DEADLINE_S == 10
    assert agent.PROBE_TIMEOUT_S >= agent.MIN_DEADLINE_S and agent.REQUEST_TIMEOUT_S >= agent.MIN_DEADLINE_S
    agent.client()
    assert FakeClient.options.timeout >= agent.MIN_DEADLINE_S * 1000


def test_a_failed_probe_says_why(monkeypatch, caplog):
    monkeypatch.setattr(agent, "client", lambda: SimpleNamespace(models=SimpleNamespace(
        generate_content=lambda **kw: (_ for _ in ()).throw(RuntimeError("400 INVALID_ARGUMENT deadline too short")))))
    with caplog.at_level("INFO", logger="pace"):
        assert agent._probe("gemini-3.8-flash") is False
    assert any('"event": "probe"' in r.getMessage() and '"ok": false' in r.getMessage() for r in caplog.records)
