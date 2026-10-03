"""Deterministic coaching logic. The model decides *what to say and when to adjust*; the numbers live here.

The plan is a queue of upcoming sessions (always 6 = 2 weeks, 3 sessions a week). Each logged run pops the front of
the queue and the queue refills from a list of training "levels". The agent steers the trajectory with adjust_plan.
"""
import json
from pathlib import Path

STATE_FILE = Path(__file__).parent / "state.json"
LADDER = [("5K", 5.0), ("10K", 10.0), ("Half marathon (21K)", 21.1), ("Marathon (42K)", 42.2)]
# Couch-to-5K style run/walk levels: (run_min, walk_min, reps). walk 0 means one continuous run.
INTERVAL_PROGRAM = [(1, 1, 6), (2, 2, 5), (3, 2, 5), (5, 2, 4), (8, 2, 3), (12, 2, 2), (20, 0, 1), (25, 0, 1), (30, 0, 1)]
# Gentler on-ramp before the standard program: shorter jogs, longer walks (run_min, walk_min, reps).
# Recruits start here by profile, and stepping back from week 1 lands here.
EASY_ON_RAMP = [(0.5, 2.5, 6), (0.5, 2, 8), (0.75, 1.5, 8)]
DEFAULT_EASY_PACE = 8.5  # min/km for someone who has never run
WARMUP_MIN = 5
COOLDOWN_MIN = 5
SESSIONS_PER_WEEK = 3
LOOKAHEAD = 2 * SESSIONS_PER_WEEK
PAIN_WORDS = ("pain", "hurt", "knee", "injur", "sore", "ache", "dizzy", "chest", "sprain", "shin")
BAD_FLAGS = ("incomplete", "too_hard", "too_fast", "possible_injury")


def load_state() -> dict:
    return json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def reset_state() -> None:
    STATE_FILE.unlink(missing_ok=True)


def fmt_pace(pace: float) -> str:
    minutes = int(pace)
    return f"{minutes}:{round((pace - minutes) * 60):02d} /km"


def fmt_dur(minutes: float) -> str:
    secs = round(minutes * 60)
    if secs < 60:
        return f"{secs} sec"
    if secs % 60 == 0:
        return f"{secs // 60} min"
    return f"{secs // 60} min {secs % 60} sec"


def bmi(profile: dict) -> float:
    return profile["weight_kg"] / (profile["height_cm"] / 100) ** 2


def on_ramp_start(profile: dict) -> int:
    """Which level a recruit who cannot run starts at: 0 is the gentlest, len(EASY_ON_RAMP) is the standard week 1."""
    if bmi(profile) >= 35 or profile["body_fat_pct"] >= 40:
        return 0
    if bmi(profile) >= 30 or profile["body_fat_pct"] >= 35:
        return 1
    if profile["age"] >= 55:
        return 2
    return len(EASY_ON_RAMP)


def is_high_risk(profile: dict) -> bool:
    return profile["body_fat_pct"] >= 30 or profile["age"] >= 55


def pace_limit(state: dict) -> float:
    """Fastest pace (min/km) we tolerate on a training run. Stricter for high-risk profiles."""
    margin = 0.96 if is_high_risk(state["profile"]) else 0.92
    return state["easy_pace"] * margin


# ---------- plan construction ----------

def _ladder_levels(start_long_km: float) -> list:
    """Long-run distance per level, +0.5 km steps while short, then +10%, landing exactly on each milestone."""
    targets = [km for _, km in LADDER]
    longs, cur = [], start_long_km
    while True:
        longs.append(round(cur, 1))
        if cur >= targets[-1]:
            break
        nxt = cur + 0.5 if cur < 5 else cur * 1.1
        for t in targets:
            if cur < t <= nxt:
                nxt = t
                break
        cur = nxt
    return [{"phase": "ladder", "long_km": km} for km in longs]


def _make_session(levels: list, seq: int, level_idx: int, slot: int) -> dict:
    level = levels[min(level_idx, len(levels) - 1)]
    session = {"id": seq, "level": level_idx, "slot": slot,
               "week": seq // SESSIONS_PER_WEEK + 1, "day": seq % SESSIONS_PER_WEEK + 1}
    if level["phase"] == "intervals":
        if level["walk"]:
            session.update(kind="intervals", run_min=level["run"], walk_min=level["walk"], reps=level["reps"])
        else:
            session.update(kind="continuous_time", run_min=level["run"])
    else:
        is_long = slot == SESSIONS_PER_WEEK - 1
        km = level["long_km"] if is_long else round(max(1.0, level["long_km"] * 0.6), 1)
        session.update(kind="distance", km=km, is_long=is_long)
    return session


def _extend(state: dict) -> None:
    c = state["cursor"]
    while len(state["upcoming"]) < LOOKAHEAD:
        state["upcoming"].append(_make_session(state["levels"], c["seq"], c["level"], c["slot"]))
        c["seq"] += 1
        c["slot"] += 1
        if c["slot"] == SESSIONS_PER_WEEK:
            c["slot"] = 0
            c["level"] = min(c["level"] + 1, len(state["levels"]) - 1)


def _replan(state: dict, level_idx: int) -> None:
    state["cursor"] = {"seq": state["upcoming"][0]["id"], "level": level_idx, "slot": 0}
    state["upcoming"] = []
    _extend(state)


def label(s: dict) -> str:
    return f"Week {s['week']}, Day {s['day']}"


def describe(s: dict) -> str:
    if s["kind"] == "intervals":
        return f"{s['reps']} x ({fmt_dur(s['run_min'])} run + {fmt_dur(s['walk_min'])} walk)"
    if s["kind"] == "continuous_time":
        return f"{s['run_min']} min non-stop run"
    return f"{s['km']} km {'long' if s['is_long'] else 'easy'} run"


def explain(state: dict, s: dict) -> dict:
    """Detailed breakdown of one session: timeline blocks for the bar chart plus step-by-step instructions."""
    easy, limit = state["easy_pace"], pace_limit(state)
    blocks = [{"type": "warmup", "minutes": WARMUP_MIN}]
    steps = [f"Warm up: {WARMUP_MIN} minutes of brisk walking. Not a stroll. Get the blood moving."]
    if s["kind"] == "intervals":
        for i in range(s["reps"]):
            blocks.append({"type": "run", "minutes": s["run_min"]})
            if i < s["reps"] - 1:
                blocks.append({"type": "walk", "minutes": s["walk_min"]})
        steps.append(f"Run {fmt_dur(s['run_min'])} at a pace where you could still speak in sentences, "
                     f"then walk {fmt_dur(s['walk_min'])}. Repeat {s['reps']} times, finishing on a run.")
        steps.append("Run segments should feel like 5 to 6 out of 10. If you cannot talk, slow down. "
                     "Slow is the whole point.")
        run_minutes = round(s["run_min"] * s["reps"], 1)
    elif s["kind"] == "continuous_time":
        blocks.append({"type": "run", "minutes": s["run_min"]})
        steps.append(f"Run {s['run_min']} minutes without stopping, as slowly as you need. Slow beats stopping.")
        steps.append("Effort 5 to 6 out of 10. You should be able to speak a short sentence.")
        run_minutes = s["run_min"]
    else:
        run_minutes = max(1, round(s["km"] * easy))
        blocks.append({"type": "run", "minutes": run_minutes, "label": f"{s['km']} km"})
        steps.append(f"Run {s['km']} km at about {fmt_pace(easy)}. "
                     f"Do not go faster than {fmt_pace(limit)}, that limit is there to keep you running for years.")
        steps.append("Effort 5 to 6 out of 10, even on the long run. Steady beats heroic.")
    blocks.append({"type": "cooldown", "minutes": COOLDOWN_MIN})
    steps.append(f"Cool down: {COOLDOWN_MIN} minutes of easy walking, then stretch calves and hamstrings.")
    return {"id": s["id"], "label": label(s), "week": s["week"], "day": s["day"], "kind": s["kind"],
            "summary": describe(s), "blocks": blocks, "steps": steps,
            "total_minutes": round(sum(b["minutes"] for b in blocks), 1), "run_minutes": run_minutes,
            "reps": s.get("reps"), "run_min": s.get("run_min"), "km": s.get("km")}


def _brief(s: dict) -> dict:
    return {"id": s["id"], "label": label(s), "summary": describe(s)}


# ---------- tools the agent can call ----------

def save_profile(
    age: int,
    weight_kg: float,
    height_cm: float,
    body_fat_pct: float,
    longest_run_km: float,
    pace_min_per_km: float,
) -> dict:
    """Save the recruit's profile, place them on the training ladder and build their first two weeks of runs.

    Args:
        age: Age in years.
        weight_kg: Body weight in kilograms.
        height_cm: Height in centimetres.
        body_fat_pct: Body fat percentage.
        longest_run_km: Longest single run they did recently, in km. Use 0 if they cannot run at all.
        pace_min_per_km: Their pace on that run in minutes per km (e.g. 6.5 for 6:30/km). Use 0 if they cannot run.
    """
    flags = []
    if longest_run_km > 42.2 or (pace_min_per_km and pace_min_per_km < 3.5):
        flags.append("implausible_claim: distance or pace is not believable, call them out")
    if longest_run_km < 1:
        longest_run_km, pace_min_per_km = 0.0, 0.0

    easy_pace = pace_min_per_km * 1.1 if pace_min_per_km else DEFAULT_EASY_PACE
    profile = {"age": age, "weight_kg": weight_kg, "height_cm": height_cm, "body_fat_pct": body_fat_pct,
               "longest_run_km": longest_run_km, "pace_min_per_km": pace_min_per_km}
    start_level, ramp = 0, len(EASY_ON_RAMP)
    if longest_run_km < 2:  # cannot really run yet: run/walk program first, then the km ladder
        levels = [{"phase": "intervals", "run": r, "walk": w, "reps": n} for r, w, n in EASY_ON_RAMP + INTERVAL_PROGRAM]
        start_level = on_ramp_start(profile) if longest_run_km < 1 else ramp + 3
        levels += _ladder_levels(round(30 / easy_pace, 1))
    else:
        levels = _ladder_levels(max(1.5, round(longest_run_km * 0.9, 1)))

    state = {
        "profile": profile,
        "easy_pace": easy_pace,
        "levels": levels,
        "cursor": {"seq": 0, "level": start_level, "slot": 0},
        "upcoming": [],
        "history": [],
        "milestones": [name for name, km in LADDER if km <= longest_run_km],
        "program_complete": False,
        "last_advance_id": -99,
    }
    _extend(state)
    save_state(state)
    return {"flags": flags, "high_risk_profile": is_high_risk(state["profile"]),
            "starts_with_run_walk": levels[0]["phase"] == "intervals",
            "gentle_start": start_level < ramp and longest_run_km < 1, "bmi": round(bmi(profile), 1),
            "easy_pace": fmt_pace(easy_pace), "pace_limit_do_not_beat": fmt_pace(pace_limit(state)),
            "first_run": explain(state, state["upcoming"][0]),
            "upcoming": [_brief(s) for s in state["upcoming"]]}


def get_status() -> dict:
    """Return the recruit's profile, next run, upcoming plan, milestones and recent runs."""
    state = load_state()
    if not state:
        return {"error": "no recruit on file yet, run onboarding"}
    return {"profile": state["profile"], "high_risk_profile": is_high_risk(state["profile"]),
            "next_run": explain(state, state["upcoming"][0]),
            "upcoming": [_brief(s) for s in state["upcoming"]],
            "recent_runs": state["history"][-5:], "milestones_reached": state["milestones"],
            "run_walk_program_complete": state["program_complete"]}


def log_run(
    session_id: int,
    completed: float,
    effort: int,
    distance_km: float = 0.0,
    duration_min: float = 0.0,
    notes: str = "",
) -> dict:
    """Log the recruit's NEXT run and check it against the plan and the safety guardrails.

    Args:
        session_id: The id of the next run (must be the first upcoming session).
        completed: For interval sessions, how many run intervals they finished. For non-stop timed runs, how many
            minutes they ran without stopping. Ignored (pass 0) for distance runs.
        effort: How hard it felt, 1 (very easy) to 10 (all out). Easy running should be 5 to 6.
        distance_km: Distance run, only for distance runs, otherwise 0.
        duration_min: Total time in minutes, only for distance runs, otherwise 0.
        notes: Anything the recruit said about it (pain, tiredness, etc).
    """
    state = load_state()
    if not state:
        return {"error": "no recruit on file yet"}
    s = state["upcoming"][0]
    if s["id"] != session_id:
        return {"error": f"session {session_id} is not the next run, the next run is session {s['id']}"}

    flags = []
    if s["kind"] == "intervals":
        target, done = s["reps"], min(completed, s["reps"])
    elif s["kind"] == "continuous_time":
        target, done = s["run_min"], min(completed, s["run_min"])
    else:
        target, done = s["km"], distance_km
    pct = round(100 * done / target) if target else 0
    if pct < 80:
        flags.append(f"incomplete: only {pct}% of the planned work")

    effort = max(1, min(10, int(effort)))
    high_risk = is_high_risk(state["profile"])
    if effort >= (7 if high_risk else 8):
        flags.append(f"too_hard ({'high_risk_profile' if high_risk else 'normal_profile'}): "
                     f"effort {effort}/10, easy running should be 5 to 6")

    pace = None
    if s["kind"] == "distance" and distance_km > 0 and duration_min > 0:
        pace = duration_min / distance_km
        if pace < pace_limit(state):
            flags.append(f"too_fast ({'high_risk_profile' if high_risk else 'normal_profile'}): "
                         f"pace {fmt_pace(pace)} beats the limit {fmt_pace(pace_limit(state))}")
        if distance_km > s["km"] * 1.15:
            flags.append(f"overran: planned {s['km']} km, ran {distance_km} km")
    injury = bool(notes) and any(w in notes.lower() for w in PAIN_WORDS)
    if injury:
        flags.append("possible_injury: tell them to stop running until it passes and see a doctor if it persists")
    if notes:
        flags.append(f"recruit_note: {notes}")
    prev_shaky = bool(state["history"]) and (state["history"][-1].get("skipped") or
                                              any(f.startswith(BAD_FLAGS) for f in state["history"][-1]["flags"]))
    recommend = None
    if s["kind"] != "distance" and (pct < 80 or effort >= 9 or injury):
        recommend = ("step_back: they struggled, give them longer walk breaks, do not hesitate" if (prev_shaky or pct < 60 or injury)
                     else "repeat: they struggled a little, replay this level")

    entry = {"id": s["id"], "label": label(s), "summary": describe(s), "completion_pct": pct, "effort": effort,
             "pace": fmt_pace(pace) if pace else None, "flags": flags}
    state["history"].append(entry)
    state["upcoming"].pop(0)
    _extend(state)

    milestone = None
    if s["kind"] == "distance" and s["is_long"]:
        for name, km in LADDER:
            if name not in state["milestones"] and distance_km >= km:
                state["milestones"].append(name)
                milestone = name
    if s["kind"] == "continuous_time" and s["run_min"] >= 30 and pct >= 100 and not state["program_complete"]:
        state["program_complete"] = True
        milestone = "Run/walk program complete (30 min non-stop)"
    save_state(state)
    return {"logged": entry, "recommend": recommend, "milestone_just_reached": milestone,
            "recent_runs": state["history"][-3:],
            "next_run": _brief(state["upcoming"][0])}


def skip_run(reason: str = "") -> dict:
    """Record that the recruit skipped the NEXT run. The same run stays next in the plan.

    Args:
        reason: Their excuse, if they gave one.
    """
    state = load_state()
    if not state:
        return {"error": "no recruit on file yet"}
    s = state["upcoming"][0]
    state["history"].append({"id": s["id"], "label": label(s), "summary": describe(s), "skipped": True,
                             "completion_pct": 0, "effort": None, "pace": None,
                             "flags": ["skipped" + (f": {reason}" if reason else "")]})
    save_state(state)
    in_a_row = 0
    for h in reversed(state["history"]):
        if not h.get("skipped"):
            break
        in_a_row += 1
    return {"skipped_in_a_row": in_a_row, "next_run": _brief(s)}


def adjust_plan(mode: str, reason: str) -> dict:
    """Change the trajectory of the upcoming runs. Only call this when the plan should change.

    Args:
        mode: "advance" jumps to the next training level now (code blocks it after a bad run or if the last advance
            was less than 3 runs ago). "repeat" replays the current level from its start. "step_back" drops to the
            previous level, which in the run/walk program means shorter jogs and longer walk breaks. "continue" changes nothing.
        reason: One short sentence on why (shown to the recruit).
    """
    state = load_state()
    if not state:
        return {"error": "no recruit on file yet"}
    if mode not in ("advance", "repeat", "step_back", "continue"):
        return {"error": "mode must be advance, repeat, step_back or continue"}
    cur = state["upcoming"][0]
    last = state["history"][-1] if state["history"] else None
    result = {"mode": mode, "reason": reason}

    if mode == "continue":
        return {**result, "upcoming": [_brief(s) for s in state["upcoming"]]}
    if mode == "advance":
        bad_last = last and (last.get("skipped") or any(f.startswith(BAD_FLAGS) for f in last["flags"]))
        if bad_last or cur["id"] - state["last_advance_id"] < SESSIONS_PER_WEEK:
            return {**result, "applied": False,
                    "blocked": "advance blocked: the last run was not clean, or the last advance was under 3 runs ago"}
        level = min(cur["level"] + 1, len(state["levels"]) - 1)
        state["last_advance_id"] = cur["id"]
    elif mode == "repeat":
        level = cur["level"]
    else:
        level = max(0, cur["level"] - 1)
    _replan(state, level)
    save_state(state)
    return {**result, "applied": True, "upcoming": [_brief(s) for s in state["upcoming"]]}


ALL_TOOLS = [save_profile, get_status, log_run, skip_run, adjust_plan]
