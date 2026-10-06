"""The privacy notice makes promises: how long data is kept, what Google does with it, that you can download and delete it.
These tests tie each promise to the real behaviour, so the notice cannot drift away from what the app does."""
import json
import os
import re
import time

import pytest

import server
import tools


class FakeCoach:
    model = "fake-model"

    def send(self, text, on_note=None):
        if text.startswith("[Intake") and not tools.load_state():
            tools.save_profile(age=30, weight_kg=85, height_cm=178, body_fat_pct=26, longest_run_km=0, pace_min_per_km=0)
        return "Move it, recruit.", []


@pytest.fixture
def web(tmp_path, monkeypatch):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    cache = tmp_path / "tts"
    cache.mkdir()
    monkeypatch.setattr(server, "STATE_DIR", sessions)
    monkeypatch.setattr(server.voice, "CACHE", cache)
    monkeypatch.setattr(server, "new_coach", FakeCoach)
    monkeypatch.setattr(server, "limiter", server.Limiter())
    monkeypatch.setattr(server, "SESSIONS", server.OrderedDict())
    monkeypatch.setattr(server, "_last_prune", time.time())
    return server


def visitor(ip="1.1.1.1"):
    client = server.app.test_client()
    client.environ_base["REMOTE_ADDR"] = ip
    return client


def onboard(client):
    return client.post("/api/chat", json={"message": "[Intake form submitted] 30, 85 kg"})


# ---------- the notice itself ----------

def test_notice_is_served_and_has_no_unfilled_placeholders(web):
    r = visitor().get("/privacy")
    text = r.get_data(as_text=True)
    assert r.status_code == 200 and r.mimetype == "text/html"
    assert "{{" not in text and "}}" not in text


def test_retention_days_in_the_notice_are_the_real_ones(web, monkeypatch):
    monkeypatch.setattr(server, "STATE_TTL_DAYS", 9)
    text = visitor().get("/privacy").get_data(as_text=True)
    assert "<b>9 days</b>" in text and "Deleted after 9 days" in text


def test_cookie_lifetime_in_the_notice_matches_the_cookie(web):
    client = visitor()
    cookie = client.get("/api/state").headers["Set-Cookie"]
    max_age = int(re.search(r"Max-Age=(\d+)", cookie).group(1))
    assert max_age == server.COOKIE_DAYS * 86400
    assert f"{server.COOKIE_DAYS} days" in client.get("/privacy").get_data(as_text=True)


def test_free_tier_notice_warns_that_google_may_read_the_content(web, monkeypatch):
    monkeypatch.setattr(server, "PAID_GEMINI", False)
    text = visitor().get("/privacy").get_data(as_text=True)
    assert "free tier" in text and "human reviewers may read" in text and "improve its products" in text
    assert visitor().get("/api/state").json["free_tier"] is True


def test_paid_notice_does_not_claim_google_reads_or_trains_on_it(web, monkeypatch):
    monkeypatch.setattr(server, "PAID_GEMINI", True)
    text = visitor().get("/privacy").get_data(as_text=True)
    assert "human reviewers" not in text and "does not use prompts or responses" in text
    assert visitor().get("/api/state").json["free_tier"] is False


def test_notice_names_the_rights_the_app_actually_provides(web):
    text = visitor().get("/privacy").get_data(as_text=True)
    for promise in ("Download my data", "Reset recruit", "IMY", "explicit consent", "not medical advice"):
        assert promise.lower() in text.lower(), promise


# ---------- the promise: you can download your data, and only yours ----------

def test_download_returns_the_visitors_own_data_as_a_file(web):
    a = visitor("1.1.1.1")
    onboard(a)
    r = a.get("/api/export")
    assert r.status_code == 200 and r.mimetype == "application/json"
    assert "attachment" in r.headers["Content-Disposition"]
    body = json.loads(r.get_data(as_text=True))
    assert body["data"]["profile"]["weight_kg"] == 85 and "exported_at" in body


def test_download_never_returns_someone_elses_data(web):
    a, b = visitor("1.1.1.1"), visitor("2.2.2.2")
    onboard(a)
    assert b.get("/api/export").status_code == 404          # B has nothing, and cannot reach A's file


def test_download_before_any_data_is_a_clean_404(web):
    assert visitor().get("/api/export").status_code == 404


# ---------- the promise: reset deletes, nothing outlives the retention period ----------

def test_reset_deletes_the_stored_file(web):
    a = visitor()
    onboard(a)
    assert list(server.STATE_DIR.glob("*.json"))
    a.post("/api/reset")
    assert not list(server.STATE_DIR.glob("*.json"))
    assert a.get("/api/export").status_code == 404


def test_cached_speech_expires_with_the_retention_period(web, monkeypatch):
    old, fresh = server.voice.CACHE / "old.wav", server.voice.CACHE / "fresh.wav"
    old.write_bytes(b"x" * 2000), fresh.write_bytes(b"x" * 2000)
    ancient = time.time() - 40 * 86400
    os.utime(old, (ancient, ancient))
    monkeypatch.setattr(server, "_last_prune", 0.0)
    visitor().get("/healthz")
    assert not old.exists() and fresh.exists()


def test_the_notice_page_is_not_indexed_and_needs_no_cookie(web):
    r = visitor().get("/privacy")
    assert "noindex" in r.get_data(as_text=True)
    assert "Set-Cookie" not in r.headers
