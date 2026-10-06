import pytest

import agent
import tools


@pytest.fixture(autouse=True)
def scratch_state(tmp_path, monkeypatch):
    """Every test gets its own empty state file, so tests never touch a real recruit's plan."""
    monkeypatch.setattr(tools, "STATE_FILE", tmp_path / "state.json")
    agent._good.update(idx=0, at=0.0)  # which model the last conversation fell back to must not leak between tests
    tools._state_file.set(None)  # the web server pins a per-visitor file for the current thread: never let that leak between tests


BEGINNER = dict(age=30, weight_kg=85, height_cm=178, body_fat_pct=26, longest_run_km=0, pace_min_per_km=0)
RUNNER = dict(age=34, weight_kg=72, height_cm=175, body_fat_pct=18, longest_run_km=6, pace_min_per_km=6.0)


def onboard(**overrides):
    """Create a recruit. Defaults to a beginner who cannot run yet."""
    profile = {**BEGINNER, **overrides}
    return tools.save_profile(**profile)


def next_id():
    return tools.load_state()["upcoming"][0]["id"]


def log_clean_run(effort=5):
    """Log the next run as fully completed at a comfortable effort, whatever kind of session it is."""
    s = tools.load_state()["upcoming"][0]
    if s["kind"] == "distance":
        pace = tools.load_state()["easy_pace"]
        return tools.log_run(s["id"], 0, effort, distance_km=s["km"], duration_min=round(s["km"] * pace, 1))
    full = s.get("reps") or s.get("run_min")
    return tools.log_run(s["id"], full, effort)
