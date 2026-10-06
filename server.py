import functools
import json
import logging
import math
import os
import re
import secrets
import threading
import time
from collections import OrderedDict, defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, Response, abort, g, jsonify, request, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

import agent
import sim
import tools
import voice

logging.basicConfig(level=logging.INFO, format="%(message)s")

PUBLIC = os.getenv("SP_PUBLIC") == "1"  # on the open internet: hide the dev pages, hide error details, cache static files
STATE_DIR = Path(os.getenv("SP_STATE_DIR") or Path(__file__).parent / "sessions")
STATE_TTL_DAYS = float(os.getenv("SP_STATE_TTL_DAYS", "14"))  # a recruit nobody touched for this long is forgotten
MAX_SESSIONS = int(os.getenv("SP_MAX_SESSIONS", "100"))       # live conversations kept in memory; their files stay on disk
MAX_CHAT_CHARS = 600
COOKIE = "sp_sid"
SID_RE = re.compile(r"^[A-Za-z0-9_-]{22}$")  # what secrets.token_urlsafe(16) makes; anything else is never used as a file name

# Per client IP: (requests, seconds). Per day, across everyone: how many of that kind of call we pay for.
RATE = {"coach": (int(os.getenv("SP_RATE_COACH", "30")), 600), "speak": (int(os.getenv("SP_RATE_SPEAK", "60")), 600),
        "transcribe": (int(os.getenv("SP_RATE_TRANSCRIBE", "15")), 600)}
DAILY = {"coach": int(os.getenv("SP_DAILY_COACH", "400")), "speak": int(os.getenv("SP_DAILY_SPEAK", "300")),
         "transcribe": int(os.getenv("SP_DAILY_TRANSCRIBE", "100"))}

app = Flask(__name__, static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 9_000_000  # the biggest legitimate body is a spoken reply
if os.getenv("SP_TRUST_PROXY") == "1":  # only behind our own reverse proxy, otherwise clients could fake their IP
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
STATE_DIR.mkdir(parents=True, exist_ok=True)


# ---------- spending limits ----------

class Limiter:
    """Sliding-window limit per client IP plus a daily cap for the whole site. In memory: a restart resets the day's count."""

    def __init__(self):
        self.lock = threading.Lock()
        self.hits = defaultdict(deque)
        self.day = None
        self.used = defaultdict(int)

    def check(self, group: str, ip: str, now: float | None = None) -> tuple[bool, int, str]:
        """Returns (allowed, retry_after_seconds, reason). A refused call is not counted."""
        now = now if now is not None else time.time()
        utc = datetime.fromtimestamp(now, timezone.utc)
        with self.lock:
            if utc.date() != self.day:
                self.day, self.used = utc.date(), defaultdict(int)
            if self.used[group] >= DAILY[group]:
                tomorrow = (utc + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                return False, int((tomorrow - utc).total_seconds()), "daily"
            limit, window = RATE[group]
            q = self.hits[(group, ip)]
            while q and q[0] <= now - window:
                q.popleft()
            if len(q) >= limit:
                return False, int(q[0] + window - now) + 1, "rate"
            q.append(now)
            self.used[group] += 1
            if len(self.hits) > 5000:  # forget clients that went quiet
                for k in [k for k, v in self.hits.items() if not v or v[-1] <= now - 3600]:
                    del self.hits[k]
            return True, 0, ""


limiter = Limiter()
OFF_DUTY = {"daily": "Sergeant Pace is off duty for today, recruit. Report back tomorrow.",
            "rate": "Easy, recruit. You are asking for too much, too fast. Catch your breath and try again in {mins} min."}


def limited(group: str):
    """Decorator for routes that cost money: refuse with an in-character 429 when a limit is hit."""
    def wrap(fn):
        @functools.wraps(fn)
        def inner(*args, **kwargs):
            ok, retry, reason = limiter.check(group, request.remote_addr or "?")
            if not ok:
                resp = jsonify({"error": OFF_DUTY[reason].format(mins=max(1, math.ceil(retry / 60))), "reason": reason})
                resp.status_code = 429
                resp.headers["Retry-After"] = str(retry)
                return resp
            return fn(*args, **kwargs)
        return inner
    return wrap


# ---------- one recruit per visitor ----------

class Session:
    def __init__(self):
        self.lock = threading.Lock()  # one turn at a time per visitor, so a double click cannot interleave two plan changes
        self.coach = None


SESSIONS: OrderedDict[str, Session] = OrderedDict()
SESSIONS_LOCK = threading.Lock()
_last_prune = 0.0


def get_session(sid: str) -> Session:
    with SESSIONS_LOCK:
        s = SESSIONS.get(sid)
        if s is None:
            s = SESSIONS[sid] = Session()
        SESSIONS.move_to_end(sid)
        while len(SESSIONS) > MAX_SESSIONS:
            idle = next((k for k, v in SESSIONS.items() if k != sid and not v.lock.locked()), None)
            if idle is None:
                break
            del SESSIONS[idle]  # forgets the chat history only; the recruit's file stays and the next turn rebuilds the coach
        return s


def prune_state_files() -> None:
    global _last_prune
    if time.time() - _last_prune < 3600:
        return
    _last_prune = time.time()
    cutoff = time.time() - STATE_TTL_DAYS * 86400
    for f in STATE_DIR.glob("*.json"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
        except OSError:
            pass


def new_coach():
    return agent.Coach()


@app.before_request
def identify():
    sid = request.cookies.get(COOKIE, "")
    g.new_sid = not SID_RE.match(sid)
    g.sid = secrets.token_urlsafe(16) if g.new_sid else sid
    tools.use_state_file(STATE_DIR / f"{g.sid}.json")
    prune_state_files()


@app.after_request
def finish(resp):
    if request.path.startswith("/api/") and g.get("new_sid"):
        resp.set_cookie(COOKIE, g.sid, max_age=30 * 86400, httponly=True, samesite="Lax", secure=request.is_secure)
    if request.path.startswith("/api/") or not PUBLIC:
        resp.headers["Cache-Control"] = "no-store"  # a demo you keep editing, and answers that are one visitor's own
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("Permissions-Policy", "microphone=(self), camera=(), geolocation=()")
    return resp


# ---------- views ----------

def state_view() -> dict:
    state = tools.load_state()
    if not state:
        return {"onboarded": False, "public": PUBLIC}
    return {
        "onboarded": True,
        "public": PUBLIC,
        "easy_pace": tools.fmt_pace(state["easy_pace"]),
        "pace_limit": tools.fmt_pace(tools.pace_limit(state)),
        "ladder": [{"name": n, "km": km} for n, km in tools.LADDER],
        "milestones": state["milestones"],
        "estimates": tools.estimate_milestones(state),
        "weighin_due": tools.weighin_due(state),
        "body": {"weight_kg": state["profile"]["weight_kg"], "body_fat_pct": state["profile"]["body_fat_pct"], "log": tools._body_log(state)},
        "program_complete": state["program_complete"],
        "next": tools.explain(state, state["upcoming"][0]),
        "upcoming": [{"id": s["id"], "week": s["week"], "day": s["day"], "summary": tools.describe(s)}
                     for s in state["upcoming"]],
        "history": state["history"][-6:],
    }


def turn(message: str, **extra):
    session = get_session(g.sid)
    with session.lock:
        prior = state_view()
        before, before_est = prior.get("upcoming", []), prior.get("estimates", [])  # lets the page show what the agent changed
        started = time.time()
        try:
            if session.coach is None:
                session.coach = new_coach()
            reply, trace = session.coach.send(message)
        except Exception as e:
            logging.getLogger("pace").exception("turn failed")
            logging.info(json.dumps({"event": "turn", "sid": g.sid[:6], "route": request.path, "ok": False,
                                     "ms": round((time.time() - started) * 1000), "error": type(e).__name__}))
            return jsonify({"error": "The sergeant is unavailable right now. Try again in a minute." if PUBLIC else str(e)}), 502
        logging.info(json.dumps({"event": "turn", "sid": g.sid[:6], "route": request.path, "ok": True, "model": session.coach.model,
                                 "ms": round((time.time() - started) * 1000), "tools": [t["tool"] for t in trace]}))
        return jsonify({"reply": reply, "trace": trace, "model": session.coach.model, "state": state_view(),
                        "before": before, "before_estimates": before_est, **extra})


def next_session():
    state = tools.load_state()
    return state["upcoming"][0] if state else None


def number(value, default=0.0, lo=0.0, hi=1000.0) -> float:
    """A float from the client, clamped. NaN and infinity would reach the maths otherwise."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return min(max(v, lo), hi) if math.isfinite(v) else default


def body_json() -> dict:
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else {}


def dev_only():
    if PUBLIC:
        abort(404)


@app.get("/healthz")
def healthz():
    return jsonify({"ok": True})


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.get("/api/state")
def get_state():
    return jsonify(state_view())


@app.post("/api/chat")
@limited("coach")
def post_chat():
    message = str(body_json().get("message", "")).strip()[:MAX_CHAT_CHARS]
    if not message:
        return jsonify({"error": "Say something, recruit."}), 400
    return turn(message)


@app.post("/api/run")
@limited("coach")
def post_run():
    s = next_session()
    if not s:
        return jsonify({"error": "Finish the intake form first, recruit."}), 400
    body = body_json()
    form = {"completed": number(body.get("completed")), "effort": int(number(body.get("effort"), 5, 1, 10)),
            "distance_km": number(body.get("distance_km")), "duration_min": number(body.get("duration_min")),
            "notes": str(body.get("notes", "")).strip()[:300]}
    return turn(sim.report_message(s, form))


@app.post("/api/weighin")
@limited("coach")
def post_weighin():
    state = tools.load_state()
    if not state:
        return jsonify({"error": "Finish the intake form first, recruit."}), 400
    body = body_json()
    return turn(sim.weighin_message(number(body.get("weight_kg")), number(body.get("body_fat_pct"))))


@app.post("/api/weighin/skip")
def post_weighin_skip():
    tools.snooze_weighin()
    return jsonify(state_view())


@app.post("/api/skip")
@limited("coach")
def post_skip():
    s = next_session()
    if not s:
        return jsonify({"error": "Finish the intake form first, recruit."}), 400
    return turn(sim.skip_message(s, str(body_json().get("notes", "")).strip()[:300]))


@app.post("/api/sim")
@limited("coach")
def post_sim():
    state = tools.load_state()
    if not state:
        return jsonify({"error": "Finish the intake form first, recruit."}), 400
    s = state["upcoming"][0]
    form = sim.sim_form(state, body_json().get("scenario"))
    text = sim.report_message(s, form) if form else sim.skip_message(s, "felt lazy")
    return turn(text, sent=text)


@app.get("/ad")
def ad_page():
    return send_from_directory("static", "ad.html")


@app.get("/voices")
def voices_page():
    dev_only()
    return send_from_directory("static", "voices.html")


@app.get("/api/voices")
def get_voices():
    dev_only()
    return jsonify({"voices": [{"name": n, "tone": t, "likely": l} for n, t, l in voice.VOICES],
                    "styles": [{"id": k, "label": v[0]} for k, v in voice.STYLES.items()], "current": voice.current()})


@app.post("/api/voice")
def post_voice():
    dev_only()  # this choice is global to the whole server
    body = body_json()
    try:
        return jsonify(voice.choose(body.get("voice", ""), body.get("style", "")))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.post("/api/speak")
@limited("speak")
def post_speak():
    body = body_json()
    text = str(body.get("text", "")).strip()[:700]
    if not text:
        return jsonify({"error": "nothing to say"}), 400
    try:
        # the voice page auditions other voices; on the public site everyone gets the issued one, which is also what the cache holds
        pick = (None, None) if PUBLIC else (body.get("voice"), body.get("style"))
        return Response(voice.speak(text, *pick), mimetype="audio/wav")
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:  # quota or model trouble: the page just stays silent
        logging.getLogger("pace").exception("speak failed")
        return jsonify({"error": "no voice right now"}), 502


@app.post("/api/transcribe")
@limited("transcribe")
def post_transcribe():
    data = request.get_data()
    if not data or len(data) > 8_000_000:
        return jsonify({"error": "no audio, or too long"}), 400
    try:
        return jsonify({"text": voice.transcribe(data, request.mimetype or "audio/wav")})
    except Exception:
        logging.getLogger("pace").exception("transcribe failed")
        return jsonify({"error": "could not hear you"}), 502


@app.post("/api/reset")
def post_reset():
    tools.reset_state()
    with SESSIONS_LOCK:
        SESSIONS.pop(g.sid, None)
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host=os.getenv("SP_HOST", "127.0.0.1"), port=int(os.getenv("SP_PORT", "8000")), debug=False)
