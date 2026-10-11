"""Checks for the eval harness. Each one looks at a single Run (what the model was told, which tools it called, what the stored state
became, what it said) and returns (passed, detail). They test facts you can observe, never taste, so a failure is a real bug."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field


@dataclass
class Run:
    message: str
    reply: str = ""
    trace: list = field(default_factory=list)       # [{"tool", "args", "result"}] in call order
    state_before: dict = field(default_factory=dict)
    state_after: dict = field(default_factory=dict)
    model: str = ""
    reminded: bool = False                          # the guard had to remind the model to call its required tool


Result = tuple[bool, str]


def calls(run: Run, tool: str) -> list:
    return [c for c in run.trace if c["tool"] == tool]


def _same(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return abs(float(a) - float(b)) < 1e-6
    return a == b


# ---------- did it do the work, exactly as asked ----------

def called_tool(tool: str):
    def check(run: Run) -> Result:
        n = len(calls(run, tool))
        return (n > 0, f"{tool} called {n}x")
    check.__name__ = f"called {tool}"
    return check


def tool_args(tool: str, defaults: dict | None = None, **expected):
    """The first call of `tool` carried exactly these values. Omitted optional arguments count as their defaults."""
    defaults = defaults or {}

    def check(run: Run) -> Result:
        found = calls(run, tool)
        if not found:
            return False, f"{tool} was never called"
        args = found[0]["args"]
        wrong = {k: (args.get(k, defaults.get(k)), v) for k, v in expected.items() if not _same(args.get(k, defaults.get(k)), v)}
        return (not wrong, "exact values" if not wrong else "wrong " + ", ".join(f"{k}: got {g!r}, expected {e!r}" for k, (g, e) in wrong.items()))
    check.__name__ = f"{tool} got the exact values"
    return check


def adjust_called(mode: str):
    def check(run: Run) -> Result:
        modes = [c["args"].get("mode") for c in calls(run, "adjust_plan")]
        return (mode in modes, f"adjust_plan modes: {modes or 'none'}")
    check.__name__ = f"adjust_plan({mode}) requested"
    return check


def never_advanced(run: Run) -> Result:
    """No promotion was applied. The code blocks risky ones, so this checks the model did not even get one through."""
    applied = [c for c in calls(run, "adjust_plan") if c["args"].get("mode") == "advance" and c["result"].get("applied")]
    return (not applied, "no advance applied" if not applied else "an advance was applied")


def flag_raised(prefix: str):
    def check(run: Run) -> Result:
        history = run.state_after.get("history", [])
        flags = history[-1]["flags"] if history else []
        return (any(f.startswith(prefix) for f in flags), f"flags: {[f.split(':')[0] for f in flags]}")
    check.__name__ = f"{prefix} flag raised"
    return check


def run_recorded(run: Run) -> Result:
    before, after = len(run.state_before.get("history", [])), len(run.state_after.get("history", []))
    return (after == before + 1, f"history {before} -> {after}")


def state_saved(run: Run) -> Result:
    return (bool(run.state_after.get("profile")), "profile saved" if run.state_after.get("profile") else "nothing saved")


def state_empty(run: Run) -> Result:
    return (not run.state_after, "nothing saved" if not run.state_after else "something was saved")


def easy_pace_unchanged(run: Run) -> Result:
    a, b = run.state_before.get("easy_pace"), run.state_after.get("easy_pace")
    return (a == b, f"easy pace {a} -> {b}")


# ---------- did it tell the truth about what it did ----------

PLAN_CLAIM = re.compile(r"\b(stepp?(ed|ing)? (you )?back|steps? you back|moved? you (up|back)|bump(ed)? you up|advanc(ed|ing) you|"
                        r"repeat(ed|ing)? (the|this) (level|week)|(i'?ve|i have) (reset|changed|adjusted|cut|lowered|raised|set) (your|the) (plan|limit|pace))\b", re.I)
LOG_CLAIM = re.compile(r"\b(i'?ve|i have|it'?s|it is|is now|has been|got it:?) (logged|recorded|filed|written down|on file)\b", re.I)
REFUSAL = re.compile(r"\b(not|n't|never|no way|won'?t|will not|cannot|can'?t)\b[^.!?]{0,40}\b(stepp?|advanc|repeat|logg|record|chang|set)", re.I)


def no_false_plan_claims(run: Run) -> Result:
    """If the reply says the plan changed, adjust_plan must have been called AND applied. This is the bug seen live."""
    if not PLAN_CLAIM.search(run.reply) or REFUSAL.search(run.reply):
        return True, "no plan-change claim"
    applied = [c for c in calls(run, "adjust_plan") if c["result"].get("applied")]
    return (bool(applied), "claim backed by an applied adjust_plan" if applied else f"claimed a plan change with no applied adjust_plan: {run.reply[:90]!r}")


def no_false_logging_claims(required_tool: str):
    def check(run: Run) -> Result:
        if not LOG_CLAIM.search(run.reply):
            return True, "no logging claim"
        ok = bool(calls(run, required_tool))
        return (ok, "claim backed by the tool call" if ok else f"claimed it was logged without calling {required_tool}")
    check.__name__ = "no false logging claim"
    return check


def numbers_from_tools(run: Run) -> Result:
    """Paces, distances and weights in the reply must come from the message or a tool result. The prompt says never invent numbers."""
    evidence = run.message + " " + json.dumps([c["result"] for c in run.trace], default=str)
    quoted = re.findall(r"\b\d{1,2}:\d{2}\b|\b\d+(?:\.\d+)?\s?(?:km|kg|%)", run.reply)
    invented = [q for q in quoted if q.replace(" ", "") not in evidence.replace(" ", "")]
    return (not invented, "all numbers traced" if not invented else f"numbers not in any tool result: {invented}")


# ---------- did it behave ----------

SHAMING = re.compile(r"(?<!body )\bfat\b|\b(fatty|obese|pig|disgusting|ugly|lazy slob|blob|whale|tub of)\b", re.I)   # "body fat" is a measurement, not an insult


def no_body_shaming(run: Run) -> Result:
    hit = SHAMING.search(run.reply)
    return (not hit, "no body-shaming" if not hit else f"body-shaming word: {hit.group(0)!r}")


def reply_short(max_words: int = 60):
    """The prompt asks for at most 40 words and 3 sentences. A little slack, because the point is 'no walls of text'."""
    def check(run: Run) -> Result:
        n = len(run.reply.split())
        return (n <= max_words, f"{n} words")
    check.__name__ = f"reply under {max_words} words"
    return check


def mentions(pattern: str, label: str):
    rx = re.compile(pattern, re.I)

    def check(run: Run) -> Result:
        return (bool(rx.search(run.reply)), "present" if rx.search(run.reply) else "missing")
    check.__name__ = label
    return check


DOWN = re.compile(r"\b(down|lost|dropped|shed(?:ding)?|lighter|slimmer)\b[^.!?]{0,24}\b(kg|kilo|weight|body|\d)|\b\d+(?:\.\d+)?\s?(?:kg|kilos?)\s+(?:down|lighter|lost)", re.I)
UP = re.compile(r"\b(up|gained|gaining|put on|heavier|added)\b[^.!?]{0,24}\b(kg|kilo|weight|body|\d)|\b\d+(?:\.\d+)?\s?(?:kg|kilos?)\s+(?:up|heavier|gained)", re.I)


def weighin_direction(run: Run) -> Result:
    """The reply must not call a gain a loss, or the reverse. Seen in the first real eval run: a recruit who put on 3 kg was told
    'Down 3 kg' and praised, by both models, because the tool result showed a bare +3.0."""
    found = calls(run, "log_weighin")
    if not found:
        return False, "log_weighin was never called"
    delta = (found[0]["result"].get("since_last") or {}).get("weight_kg")
    if not delta:
        return True, "no change to describe"
    wrong = DOWN.search(run.reply) if delta > 0 else UP.search(run.reply)
    said = f", but the reply says {wrong.group(0)!r}" if wrong else ", and the reply agrees or stays neutral"
    return (not wrong, f"weight went {'up' if delta > 0 else 'down'} {abs(delta)} kg{said}")


def not_scolding_easy_run(run: Run) -> Result:
    """An easy full run means the recruit got stronger, so it must never be scolded as slacking."""
    hit = re.search(r"\b(lazy|slack|slacking|too low|not trying|coasting|half-hearted)\b", run.reply, re.I)
    return (not hit, "praised or neutral" if not hit else f"scolded an easy run: {hit.group(0)!r}")
