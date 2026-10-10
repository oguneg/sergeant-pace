"""Regression for a bug that only appears with two visitors at once: each conversation built its own Gemini client and overwrote a
shared global, so the first client was garbage collected and closed while its request was still running."""
import threading
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
