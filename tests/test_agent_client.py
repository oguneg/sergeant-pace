"""Regression for a bug that only appears with two visitors at once: each conversation built its own Gemini client and overwrote a
shared global, so the first client was garbage collected and closed while its request was still running."""
import threading
from types import SimpleNamespace

import pytest

import agent


class FakeClient:
    created = 0

    def __init__(self, api_key=None):
        FakeClient.created += 1
        self.chats = SimpleNamespace(create=lambda **kw: SimpleNamespace(kw=kw))


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
