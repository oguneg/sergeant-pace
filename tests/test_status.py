"""Visitors are told BEFORE they fill in a form whether the sergeant can answer: daily budget spent, their own allowance used,
or Google's AI overloaded. And one person cannot drain the shared budget."""
import time

import pytest

import server
import tools


class FakeCoach:
    model = "fake-model"
    mode = "ok"            # ok | timeout | quota | other

    def send(self, text, on_note=None):
        if text.startswith("[Intake") and not tools.load_state():
            tools.save_profile(age=30, weight_kg=85, height_cm=178, body_fat_pct=26, longest_run_km=0, pace_min_per_km=0)
        if FakeCoach.mode == "timeout":
            raise TimeoutError("The read operation timed out")
        if FakeCoach.mode == "quota":
            raise RuntimeError("429 RESOURCE_EXHAUSTED")
        if FakeCoach.mode == "other":
            raise ValueError("a bug of ours")
        return "Move it, recruit.", []


@pytest.fixture
def web(tmp_path, monkeypatch):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    monkeypatch.setattr(server, "STATE_DIR", sessions)
    monkeypatch.setattr(server.voice, "CACHE", tmp_path / "tts")
    monkeypatch.setattr(server, "new_coach", FakeCoach)
    monkeypatch.setattr(server, "limiter", server.Limiter())
    monkeypatch.setattr(server, "SESSIONS", server.OrderedDict())
    monkeypatch.setattr(server, "_last_prune", time.time())
    monkeypatch.setattr(server, "PUBLIC", True)
    monkeypatch.setitem(server.UPSTREAM, "until", 0.0)
    FakeCoach.mode = "ok"
    return server


def visitor(ip="1.1.1.1"):
    client = server.app.test_client()
    client.environ_base["REMOTE_ADDR"] = ip
    return client


def chat(client, text="hello"):
    return client.post("/api/chat", json={"message": text})


def status(client):
    return client.get("/api/state").json["status"]


# ---------- healthy ----------

def test_a_fresh_site_is_available(web):
    assert status(visitor()) == {"available": True}


def test_checking_the_status_does_not_use_up_anyones_budget(web, monkeypatch):
    monkeypatch.setitem(server.DAILY, "coach", 3)
    c = visitor()
    for _ in range(20):
        status(c)
    assert [chat(c).status_code for _ in range(3)] == [200, 200, 200]      # all three real turns still available


# ---------- the site-wide daily budget ----------

def test_visitors_are_told_up_front_when_the_daily_budget_is_spent(web, monkeypatch):
    monkeypatch.setitem(server.DAILY, "coach", 2)
    chat(visitor("1.1.1.1")), chat(visitor("2.2.2.2"))
    newcomer = status(visitor("3.3.3.3"))
    assert newcomer["available"] is False and newcomer["reason"] == "daily"
    assert "budget" in newcomer["message"] and newcomer["retry_after"] > 0
    assert chat(visitor("3.3.3.3")).status_code == 429                      # and the server agrees


# ---------- one person cannot drain the shared budget ----------

def test_each_visitor_has_a_daily_allowance_of_their_own(web, monkeypatch):
    monkeypatch.setitem(server.IP_DAILY, "coach", 2)
    greedy = visitor("9.9.9.9")
    assert [chat(greedy).status_code for _ in range(2)] == [200, 200]
    over = chat(greedy)
    assert over.status_code == 429 and over.json["reason"] == "ip_daily" and "2 turns" in over.json["error"]
    s = status(greedy)
    assert s["available"] is False and s["reason"] == "ip_daily"
    assert status(visitor("8.8.8.8")) == {"available": True}                # everyone else is unaffected
    assert chat(visitor("8.8.8.8")).status_code == 200


def test_the_allowances_reset_on_a_new_day():
    lim = server.Limiter()
    day1, day2 = 1_700_000_000, 1_700_000_000 + 86400
    server.IP_DAILY["coach"], server.DAILY["coach"] = 1, 1000
    try:
        assert lim.check("coach", "ip", now=day1)[0]
        assert lim.check("coach", "ip", now=day1 + 5)[2] == "ip_daily"
        assert lim.check("coach", "ip", now=day2)[0]                       # a new day, a fresh allowance
    finally:
        server.IP_DAILY["coach"], server.DAILY["coach"] = 30, 200


# ---------- Google overloaded ----------

@pytest.mark.parametrize("mode", ["timeout", "quota"])
def test_when_google_is_struggling_the_next_visitor_is_told_before_starting(web, mode):
    FakeCoach.mode = mode
    r = chat(visitor("1.1.1.1"))
    assert r.status_code == 503 and r.json["reason"] == "upstream" and "overloaded" in r.json["error"]
    s = status(visitor("2.2.2.2"))
    assert s["available"] is False and s["reason"] == "upstream" and s["retry_after"] > 0


def test_the_warning_clears_itself_when_google_answers_again(web):
    FakeCoach.mode = "timeout"
    chat(visitor())
    assert status(visitor("2.2.2.2"))["available"] is False
    FakeCoach.mode = "ok"
    assert chat(visitor("3.3.3.3")).status_code == 200                      # the server never blocks a try, so it can recover
    assert status(visitor("4.4.4.4")) == {"available": True}


def test_the_warning_expires_on_its_own(web, monkeypatch):
    FakeCoach.mode = "quota"
    chat(visitor())
    monkeypatch.setitem(server.UPSTREAM, "until", time.time() - 1)
    assert status(visitor("2.2.2.2")) == {"available": True}


def test_our_own_bugs_do_not_pretend_to_be_google_being_busy(web):
    FakeCoach.mode = "other"
    r = chat(visitor())
    assert r.status_code == 502 and "overloaded" not in r.get_data(as_text=True)
    assert status(visitor("2.2.2.2")) == {"available": True}


def test_upstream_failures_are_logged_with_their_kind(web, caplog):
    FakeCoach.mode = "timeout"
    with caplog.at_level("INFO"):
        chat(visitor())
    assert any('"kind": "slow"' in r.getMessage() for r in caplog.records)
