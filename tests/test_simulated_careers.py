"""Run many simulated recruits through months of random runs, skips and weigh-ins, and check that the rules hold at every step.
Uses the same scenario generator as the demo (sim.py), but calls the tools directly so no model is involved."""
import random

import pytest

import sim
import tools
from conftest import onboard


def random_profile(rng):
    can_run = rng.random() < 0.5
    return dict(age=rng.randint(18, 70), weight_kg=rng.uniform(50, 130), height_cm=rng.uniform(150, 195),
                body_fat_pct=rng.uniform(8, 50),
                longest_run_km=round(rng.uniform(2, 15), 1) if can_run else 0,
                pace_min_per_km=round(rng.uniform(4.5, 8), 1) if can_run else 0)


def follow_the_tool_advice(result):
    """A well-behaved agent: do what log_run recommends. Returns the adjust_plan result, if one was made."""
    rec = (result.get("recommend") or "").split(":")[0]
    if rec in ("advance", "repeat", "step_back"):
        return tools.adjust_plan(rec, "tool advice")
    return None


@pytest.mark.parametrize("seed", range(20))
def test_rules_hold_over_a_simulated_career(seed):
    rng = random.Random(seed)
    random.seed(seed)  # sim.sim_form draws from the global generator
    onboard(**random_profile(rng))

    for step in range(45):
        state = tools.load_state()
        up = state["upcoming"]
        # the plan is always two full weeks, in order, with no gaps
        assert len(up) == tools.LOOKAHEAD
        assert [s["id"] for s in up] == list(range(up[0]["id"], up[0]["id"] + tools.LOOKAHEAD))
        assert 0 <= up[0]["level"] < len(state["levels"])
        assert all(m["weeks"] is None or m["weeks"] >= 0 for m in tools.estimate_milestones(state))

        if tools.weighin_due(state) and rng.random() < 0.7:
            p = state["profile"]
            tools.log_weighin(round(p["weight_kg"] + rng.uniform(-1.5, 1.5), 1), round(p["body_fat_pct"] + rng.uniform(-1, 1), 1))
            continue

        form = sim.sim_form(state, None)
        if form is None:
            tools.skip_run("sim")
            continue
        scenario_hurt = bool(form["notes"])
        result = tools.log_run(up[0]["id"], form["completed"], form["effort"], form["distance_km"], form["duration_min"], form["notes"])
        flags = result["logged"]["flags"]
        ceiling = tools.effort_ceiling(state["profile"])

        # rule: clearly over the effort ceiling is always called out
        if form["effort"] - ceiling > 0.75:
            assert any(f.startswith("too_hard") for f in flags)
        # rule: reported pain is always flagged, and never earns a promotion
        if scenario_hurt:
            assert any(f.startswith("possible_injury") for f in flags)
            assert not (result["recommend"] or "").startswith(("advance", "praise"))

        adjusted = follow_the_tool_advice(result)
        # rule: an advance is never applied straight after a flagged run, even if something asks for one
        if any(f.startswith(tools.BAD_FLAGS) for f in flags):
            forced = tools.adjust_plan("advance", "try to sneak a promotion in")
            assert forced["applied"] is False
            assert not (adjusted and adjusted["mode"] == "advance" and adjusted["applied"])
