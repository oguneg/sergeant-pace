"""The public face: visitors are isolated, spending is capped, nothing leaks. The model is replaced by a fake, so no key or network."""
import os
import time

import pytest

import server
import tools

INTAKE = "[Intake form submitted] age 30, 85 kg, 178 cm, 26% body fat, cannot run"


class FakeCoach:
    model = "fake-model"
    sent: list = []

    def send(self, text, on_note=None, require=None):
        FakeCoach.sent.append(text)
        if text.startswith("[Intake") and not tools.load_state():
            tools.save_profile(age=30, weight_kg=85, height_cm=178, body_fat_pct=26, longest_run_km=0, pace_min_per_km=0)
        if "EXPLODE" in text:
            raise RuntimeError("upstream said: key AIza-SECRET-123 is invalid")
        return "Move it, recruit.", [{"tool": "save_profile", "args": {}, "result": {}}]


@pytest.fixture
def web(tmp_path, monkeypatch):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    monkeypatch.setattr(server, "STATE_DIR", sessions)
    monkeypatch.setattr(server, "new_coach", FakeCoach)
    monkeypatch.setattr(server, "limiter", server.Limiter())
    monkeypatch.setattr(server, "SESSIONS", server.OrderedDict())
    monkeypatch.setattr(server, "_last_prune", time.time())
    FakeCoach.sent = []
    return server


def visitor(ip="1.1.1.1"):
    client = server.app.test_client()
    client.environ_base["REMOTE_ADDR"] = ip
    return client


def chat(client, text=INTAKE):
    return client.post("/api/chat", json={"message": text})


def test_health_check(web):
    assert visitor().get("/healthz").json == {"ok": True}


def test_each_visitor_gets_their_own_recruit(web):
    a, b = visitor("1.1.1.1"), visitor("2.2.2.2")
    assert chat(a).status_code == 200
    assert a.get("/api/state").json["onboarded"] is True
    assert b.get("/api/state").json["onboarded"] is False       # B never sees A's file
    assert len(list(server.STATE_DIR.glob("*.json"))) == 1


def test_reset_wipes_only_the_visitors_own_recruit(web):
    a, b = visitor("1.1.1.1"), visitor("2.2.2.2")
    chat(a), chat(b)
    a.post("/api/reset")
    assert a.get("/api/state").json["onboarded"] is False
    assert b.get("/api/state").json["onboarded"] is True


def test_session_cookie_is_not_readable_by_scripts(web):
    cookie = visitor().get("/api/state").headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie


@pytest.mark.parametrize("forged", ["../../etc/passwd", "..%2F..%2Fsecret", "a" * 22 + "/../x", "short", "A" * 23, ""])
def test_forged_session_ids_never_become_file_names(web, forged):
    client = visitor()
    client.set_cookie(server.COOKIE, forged)
    chat(client)
    files = list(server.STATE_DIR.parent.rglob("*.json"))
    assert len(files) == 1
    assert files[0].parent == server.STATE_DIR and server.SID_RE.match(files[0].stem)   # a fresh, well-formed id was issued instead


# ---------- spending limits ----------

def test_per_client_rate_limit_returns_an_in_character_429(web, monkeypatch):
    monkeypatch.setitem(server.RATE, "coach", (3, 600))
    a = visitor("1.1.1.1")
    assert [chat(a, f"hi {i}").status_code for i in range(3)] == [200, 200, 200]
    over = chat(a, "again")
    assert over.status_code == 429 and over.json["reason"] == "rate"
    assert int(over.headers["Retry-After"]) > 0 and "recruit" in over.json["error"]
    assert chat(visitor("9.9.9.9"), "me too").status_code == 200       # someone else is unaffected


def test_refused_calls_never_reach_the_model(web, monkeypatch):
    monkeypatch.setitem(server.RATE, "coach", (1, 600))
    a = visitor()
    chat(a, "one"), chat(a, "two"), chat(a, "three")
    assert FakeCoach.sent == ["one"]


def test_daily_cap_applies_across_all_visitors(web, monkeypatch):
    monkeypatch.setitem(server.DAILY, "coach", 2)
    assert chat(visitor("1.1.1.1"), "a").status_code == 200
    assert chat(visitor("2.2.2.2"), "b").status_code == 200
    third = chat(visitor("3.3.3.3"), "c")
    assert third.status_code == 429 and third.json["reason"] == "daily"
    assert "off duty" in third.json["error"]


def test_limiter_window_expires(monkeypatch):
    monkeypatch.setitem(server.RATE, "speak", (2, 100))
    lim = server.Limiter()
    assert lim.check("speak", "ip", now=1000)[0] and lim.check("speak", "ip", now=1001)[0]
    ok, retry, reason = lim.check("speak", "ip", now=1002)
    assert (ok, reason) == (False, "rate") and 0 < retry <= 100
    assert lim.check("speak", "ip", now=1101)[0]                   # the window has slid past the first call


def test_speak_and_transcribe_have_their_own_limits(web, monkeypatch):
    monkeypatch.setitem(server.RATE, "transcribe", (1, 600))
    monkeypatch.setattr(server.voice, "transcribe", lambda data, mime: "hello")
    c = visitor()
    assert c.post("/api/transcribe", data=b"x" * 10, content_type="audio/wav").status_code == 200
    assert c.post("/api/transcribe", data=b"x" * 10, content_type="audio/wav").status_code == 429


# ---------- nothing sensitive, nothing global ----------

def test_public_mode_hides_the_voice_tools_and_error_details(web, monkeypatch):
    monkeypatch.setattr(server, "PUBLIC", True)
    c = visitor()
    assert c.get("/voices").status_code == 404
    assert c.get("/api/voices").status_code == 404
    assert c.post("/api/voice", json={"voice": "Orus", "style": "raspy"}).status_code == 404
    boom = chat(c, "EXPLODE")
    assert boom.status_code == 502 and "AIza" not in boom.get_data(as_text=True)


def test_a_failed_turn_gets_a_fresh_coach_next_time(web, monkeypatch):
    made = []
    monkeypatch.setattr(server, "new_coach", lambda: made.append(1) or FakeCoach())
    c = visitor()
    chat(c, "one")
    chat(c, "two")
    assert len(made) == 1                      # a healthy conversation keeps its coach
    assert chat(c, "EXPLODE").status_code == 502
    chat(c, "three")
    assert len(made) == 2                      # a broken one is rebuilt, not stuck failing forever


def test_dev_mode_still_shows_the_real_error(web, monkeypatch):
    monkeypatch.setattr(server, "PUBLIC", False)
    assert "AIza-SECRET" in chat(visitor(), "EXPLODE").json["error"]


def test_public_speak_ignores_a_requested_voice(web, monkeypatch):
    monkeypatch.setattr(server, "PUBLIC", True)
    seen = {}
    monkeypatch.setattr(server.voice, "speak", lambda text, voice=None, style=None: seen.update(voice=voice, style=style) or b"RIFF")
    visitor().post("/api/speak", json={"text": "hi", "voice": "Puck", "style": "shout"})
    assert seen == {"voice": None, "style": None}


def test_security_headers_and_no_store_on_api(web):
    r = visitor().get("/api/state")
    assert r.headers["X-Content-Type-Options"] == "nosniff" and r.headers["Cache-Control"] == "no-store"


# ---------- hostile input ----------

def test_long_chat_messages_are_clipped(web):
    chat(visitor(), "x" * 5000)
    assert len(FakeCoach.sent[0]) == server.MAX_CHAT_CHARS


def test_empty_or_non_json_chat_is_a_400_not_a_crash(web):
    c = visitor()
    assert c.post("/api/chat", json={"message": "   "}).status_code == 400
    assert c.post("/api/chat", data="not json", content_type="text/plain").status_code == 400
    assert c.post("/api/chat", json=["a", "list"]).status_code == 400


@pytest.mark.parametrize("bad", ["nan", "inf", "-inf", "1e999", None, [], {"a": 1}, "'; DROP TABLE"])
def test_garbage_numbers_never_reach_the_maths(web, bad):
    c = visitor()
    chat(c)
    r = c.post("/api/run", json={"completed": bad, "effort": bad, "distance_km": bad, "duration_min": bad})
    assert r.status_code == 200
    report = FakeCoach.sent[-1].lower()
    assert "nan" not in report and "inf" not in report


def test_effort_from_the_client_is_clamped(web):
    c = visitor()
    chat(c)
    c.post("/api/run", json={"completed": 1, "effort": 9999})
    assert "Effort: 10/10" in FakeCoach.sent[-1]


def test_run_before_intake_is_refused(web):
    assert visitor().post("/api/run", json={"completed": 1, "effort": 5}).status_code == 400


# ---------- memory and disk stay bounded ----------

def test_least_recently_used_conversations_are_evicted_but_recruits_survive(web, monkeypatch):
    monkeypatch.setattr(server, "MAX_SESSIONS", 2)
    clients = [visitor(f"10.0.0.{i}") for i in range(3)]
    for c in clients:
        chat(c)
    assert len(server.SESSIONS) == 2
    assert len(list(server.STATE_DIR.glob("*.json"))) == 3                 # the evicted visitor's file is still there
    assert clients[0].get("/api/state").json["onboarded"] is True
    assert chat(clients[0], "back again").status_code == 200               # and their next turn builds a fresh coach


def test_old_state_files_are_pruned(web, monkeypatch):
    old, fresh = server.STATE_DIR / ("a" * 22 + ".json"), server.STATE_DIR / ("b" * 22 + ".json")
    old.write_text("{}"), fresh.write_text("{}")
    ancient = time.time() - 30 * 86400
    os.utime(old, (ancient, ancient))
    monkeypatch.setattr(server, "_last_prune", 0.0)
    visitor().get("/healthz")
    assert not old.exists() and fresh.exists()
