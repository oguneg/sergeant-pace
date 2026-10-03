from flask import Flask, jsonify, request, send_from_directory

import agent
import sim
import tools

app = Flask(__name__, static_folder="static")
_chat = None  # single shared conversation: one recruit per demo


def chat():
    global _chat
    if _chat is None:
        _chat = agent.Coach()
    return _chat


def state_view() -> dict:
    state = tools.load_state()
    if not state:
        return {"onboarded": False}
    return {
        "onboarded": True,
        "easy_pace": tools.fmt_pace(state["easy_pace"]),
        "pace_limit": tools.fmt_pace(tools.pace_limit(state)),
        "ladder": [{"name": n, "km": km} for n, km in tools.LADDER],
        "milestones": state["milestones"],
        "program_complete": state["program_complete"],
        "next": tools.explain(state, state["upcoming"][0]),
        "upcoming": [{"id": s["id"], "week": s["week"], "day": s["day"], "summary": tools.describe(s)}
                     for s in state["upcoming"]],
        "history": state["history"][-6:],
    }



def turn(message: str, **extra):
    try:
        reply, trace = chat().send(message)
    except Exception as e:
        return jsonify({"error": str(e)}), 502
    return jsonify({"reply": reply, "trace": trace, "model": chat().model, "state": state_view(), **extra})


def next_session():
    state = tools.load_state()
    return state["upcoming"][0] if state else None


def number(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.get("/api/state")
def get_state():
    return jsonify(state_view())


@app.post("/api/chat")
def post_chat():
    return turn(request.json["message"])


@app.post("/api/run")
def post_run():
    s = next_session()
    if not s:
        return jsonify({"error": "Finish the intake form first, recruit."}), 400
    body = request.json
    form = {"completed": number(body.get("completed")), "effort": int(number(body.get("effort"), 5)),
            "distance_km": number(body.get("distance_km")), "duration_min": number(body.get("duration_min")),
            "notes": str(body.get("notes", "")).strip()[:300]}
    return turn(sim.report_message(s, form))


@app.post("/api/skip")
def post_skip():
    s = next_session()
    if not s:
        return jsonify({"error": "Finish the intake form first, recruit."}), 400
    return turn(sim.skip_message(s, str(request.json.get("notes", "")).strip()[:300]))


@app.post("/api/sim")
def post_sim():
    state = tools.load_state()
    if not state:
        return jsonify({"error": "Finish the intake form first, recruit."}), 400
    s = state["upcoming"][0]
    form = sim.sim_form(state, request.json.get("scenario"))
    text = sim.report_message(s, form) if form else sim.skip_message(s, "felt lazy")
    return turn(text, sent=text)


@app.post("/api/reset")
def post_reset():
    global _chat
    tools.reset_state()
    _chat = None
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(port=8000, debug=False)
