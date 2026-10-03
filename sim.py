"""Messages the UI sends to the agent, plus fake run data so the demo can fast-forward."""
from __future__ import annotations

import json
import random

import tools

SCENARIOS = ["good", "hard", "skip", "hurt"]


def report_message(s: dict, f: dict) -> str:
    """Build the run report. The exact tool arguments are spelled out so the agent logs precisely what was reported."""
    lines = [f"[Run report] {tools.label(s)} (session_id={s['id']}): {tools.describe(s)}"]
    if s["kind"] == "intervals":
        lines.append(f"Run intervals completed: {f['completed']} of {s['reps']}")
    elif s["kind"] == "continuous_time":
        lines.append(f"Minutes run without stopping: {f['completed']} of {s['run_min']}")
    else:
        lines.append(f"Distance: {f['distance_km']} km in {f['duration_min']} min")
    lines.append(f"Effort: {f['effort']}/10")
    if f.get("notes"):
        lines.append(f"Notes: {f['notes']}")
    lines.append(
        f"Call log_run with session_id={s['id']}, completed={f['completed']}, effort={f['effort']}, "
        f"distance_km={f['distance_km']}, duration_min={f['duration_min']}, notes={json.dumps(f.get('notes', ''))}. "
        "Then judge this run, adjust the plan only if it should change, and preview the next run.")
    return "\n".join(lines)


def skip_message(s: dict, reason: str = "") -> str:
    return (f"[Run skipped] {tools.label(s)} (session_id={s['id']}): {tools.describe(s)}. "
            f"Reason: {reason or 'no reason given'}. Call skip_run, then respond.")


def sim_form(state: dict, scenario: str | None) -> dict | None:
    """Fake report for the next run, or None for a skip."""
    scenario = scenario if scenario in SCENARIOS else random.choice(SCENARIOS)
    if scenario == "skip":
        return None
    s, easy = state["upcoming"][0], state["easy_pace"]
    full = s.get("reps") or s.get("run_min") or 0
    form = {"completed": 0, "effort": random.choice([5, 6]), "distance_km": 0.0, "duration_min": 0.0, "notes": ""}
    if scenario == "good":
        if s["kind"] != "distance":
            form["completed"] = full
        else:
            form["distance_km"] = s["km"]
            form["duration_min"] = round(s["km"] * easy * random.uniform(0.98, 1.06), 1)
    elif scenario == "hard":
        form["effort"] = 9
        if s["kind"] != "distance":
            form["completed"] = full
        else:
            form["distance_km"] = round(s["km"] * 1.2, 1)
            form["duration_min"] = round(form["distance_km"] * easy * 0.8, 1)
    else:  # hurt
        form["effort"], form["notes"] = 7, "my knee hurts and I stopped early"
        if s["kind"] != "distance":
            form["completed"] = max(1, round(full * 0.4))
        else:
            form["distance_km"] = round(s["km"] * 0.5, 1)
            form["duration_min"] = round(form["distance_km"] * easy * 1.1, 1)
    return form
