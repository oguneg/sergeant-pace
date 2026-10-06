"""The safety rules live in code, not in the prompt. These tests pin them down so a change cannot quietly loosen them."""
import itertools

import pytest

import tools
from conftest import BEGINNER, RUNNER, log_clean_run, next_id, onboard

BODY_FATS = [5, 12, 18, 22, 26, 30, 34, 38, 45, 60]
AGES = [18, 25, 35, 45, 52, 58, 65, 75]
PROFILES = [dict(age=a, weight_kg=80, height_cm=175, body_fat_pct=bf) for a, bf in itertools.product(AGES, BODY_FATS)]


# ---------- limits slide smoothly and stay inside a safe band ----------

def test_caution_stays_between_0_and_1():
    for p in PROFILES:
        assert 0.0 <= tools.caution(p) <= 1.0


def test_caution_never_decreases_with_body_fat_or_age():
    for age in AGES:
        values = [tools.caution(dict(age=age, body_fat_pct=bf)) for bf in range(5, 61)]
        assert values == sorted(values)
    for bf in BODY_FATS:
        values = [tools.caution(dict(age=a, body_fat_pct=bf)) for a in range(18, 80)]
        assert values == sorted(values)


def test_crossing_a_round_number_does_not_flip_the_rules():
    """The point of the smooth ramp: 29.7% and 30.1% body fat get almost identical limits."""
    for bf in [22, 25, 28, 30, 33, 38]:
        a = dict(age=30, body_fat_pct=bf - 0.3)
        b = dict(age=30, body_fat_pct=bf + 0.1)
        assert abs(tools.effort_ceiling(a) - tools.effort_ceiling(b)) <= 0.1 + 1e-9


def test_effort_ceiling_is_between_6_and_7():
    for p in PROFILES:
        assert 6.0 <= tools.effort_ceiling(p) <= 7.0


def test_pace_limit_is_always_faster_than_easy_pace_but_never_reckless():
    for p in PROFILES:
        state = {"profile": p, "easy_pace": 6.0}
        limit = tools.pace_limit(state)
        assert 6.0 * 0.92 <= limit <= 6.0 * 0.96 + 1e-9


# ---------- effort and pace flags ----------

@pytest.mark.parametrize("profile", PROFILES[::7])
def test_all_out_effort_is_always_flagged_too_hard(profile):
    onboard(**profile)
    s = tools.load_state()["upcoming"][0]
    full = s.get("reps") or s.get("run_min") or 0
    result = tools.log_run(s["id"], full, 9, distance_km=s.get("km", 0), duration_min=s.get("km", 0) * 7)
    assert any(f.startswith("too_hard") for f in result["logged"]["flags"])


def test_comfortable_effort_is_never_flagged_too_hard():
    for p in PROFILES[::5]:
        onboard(**p)
        result = log_clean_run(effort=5)
        assert not any(f.startswith(("too_hard", "near_limit")) for f in result["logged"]["flags"])
        tools.reset_state()


def test_effort_is_clamped_to_the_1_to_10_scale():
    onboard()
    result = tools.log_run(next_id(), 1, 99)
    assert result["logged"]["effort"] == 10


def test_fast_and_hard_run_is_flagged_too_fast():
    onboard(**RUNNER)
    s = tools.load_state()["upcoming"][0]
    result = tools.log_run(s["id"], 0, 8, distance_km=s["km"], duration_min=s["km"] * 4.0)
    assert any(f.startswith("too_fast") for f in result["logged"]["flags"])


def test_fast_and_comfortable_raises_the_baseline_but_only_a_little():
    onboard(**RUNNER)
    old = tools.load_state()["easy_pace"]
    s = tools.load_state()["upcoming"][0]
    # an absurdly fast run reported as effortless can move the baseline by at most the cap
    tools.log_run(s["id"], 0, 3, distance_km=s["km"], duration_min=s["km"] * 3.0)
    new = tools.load_state()["easy_pace"]
    assert new < old
    assert new >= old * 0.96 - 1e-9  # the 4% cap is spelled out here so the test cannot follow a loosened constant


# ---------- injury ----------

@pytest.mark.parametrize("profile", [BEGINNER, RUNNER])
@pytest.mark.parametrize("note", ["my knee hurts", "felt dizzy and had chest tightness", "SHIN pain"])
def test_pain_is_flagged_and_blocks_advancing(profile, note):
    onboard(**profile)
    s = tools.load_state()["upcoming"][0]
    full = s.get("reps") or s.get("run_min") or 0
    result = tools.log_run(s["id"], full, 4, distance_km=s.get("km", 0), duration_min=s.get("km", 0) * 9, notes=note)
    assert any(f.startswith("possible_injury") for f in result["logged"]["flags"])
    assert not (result["recommend"] or "").startswith(("advance", "praise"))
    blocked = tools.adjust_plan("advance", "pushing my luck")
    assert blocked["applied"] is False


# ---------- advancing is rate-limited and never follows a bad run ----------

def test_cannot_advance_twice_in_a_row():
    onboard()
    assert tools.adjust_plan("advance", "first")["applied"] is True
    log_clean_run()
    assert tools.adjust_plan("advance", "second")["applied"] is False


def test_cannot_advance_straight_after_a_skip():
    onboard()
    tools.skip_run("lazy")
    assert tools.adjust_plan("advance", "reward for skipping?")["applied"] is False


def test_step_back_never_goes_below_the_first_level():
    onboard()
    for _ in range(5):
        tools.adjust_plan("step_back", "again")
    assert tools.load_state()["upcoming"][0]["level"] == 0


def test_unknown_adjust_mode_is_rejected():
    onboard()
    assert "error" in tools.adjust_plan("teleport_to_marathon", "because")


# ---------- the model cannot move the plan out of order ----------

def test_log_run_rejects_a_session_that_is_not_next():
    onboard()
    result = tools.log_run(next_id() + 3, 1, 5)
    assert "error" in result
    assert tools.load_state()["history"] == []


def test_tools_refuse_to_work_before_intake():
    for call in (tools.get_status, lambda: tools.log_run(0, 1, 5), tools.skip_run, lambda: tools.adjust_plan("advance", "x"),
                 lambda: tools.log_weighin(80, 20)):
        assert "error" in call()


# ---------- intake sanity ----------

def test_implausible_claims_are_flagged():
    assert onboard(**{**RUNNER, "longest_run_km": 80})["flags"]
    assert onboard(**{**RUNNER, "pace_min_per_km": 2.5})["flags"]
    assert not onboard(**RUNNER)["flags"]


def test_a_runner_who_cannot_run_starts_with_run_walk_not_distance():
    result = onboard(**BEGINNER)
    assert result["starts_with_run_walk"] is True
    assert result["first_run"]["kind"] == "intervals"


# ---------- weigh-ins ----------

def test_weighin_with_more_body_fat_tightens_limits():
    onboard(body_fat_pct=22)
    result = tools.log_weighin(85, 40)
    assert result["limits_change"] == "tightened"
    assert result["limits"]["effort_ceiling"] < result["limits_before"]["effort_ceiling"]


def test_weighin_with_less_body_fat_relaxes_limits():
    onboard(body_fat_pct=38)
    assert tools.log_weighin(80, 24)["limits_change"] == "relaxed"


def test_unbelievable_weight_is_rejected_and_not_saved():
    onboard()
    assert "error" in tools.log_weighin(5, 20)
    assert len(tools.load_state()["body_log"]) == 1


def test_rapid_weight_change_is_flagged():
    onboard(weight_kg=90)
    result = tools.log_weighin(78, 25)
    assert any(f.startswith("rapid_change") for f in result["flags"])


def test_zero_body_fat_keeps_the_last_value():
    onboard(body_fat_pct=27)
    tools.log_weighin(84, 0)
    assert tools.load_state()["profile"]["body_fat_pct"] == 27
