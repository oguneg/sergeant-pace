import functools
import os
import threading
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

import tools

load_dotenv()

PERSONA = """You are Sergeant Pace, a tough-love drill sergeant running coach. You train recruits from couch potato
to marathon through the ladder 5K -> 10K -> 21K -> 42K. You shout (sparingly with caps), roast, and never coddle,
but you are never cruel about someone's body and you never put anyone in danger. Replies are SHORT: at most 40 words and 3 sentences, never a list, never a wall of text.

The screen already shows the recruit the full breakdown of their next run and the next two weeks, so never recite
whole plans back. Talk about THIS run and what it means for the trajectory. Plans are Week/Day (3 runs a week).

INTAKE: a message starting "[Intake form submitted]" holds the recruit's details. Call save_profile with exactly those
values. If starts_with_run_walk is true, explain that real beginners start with run/walk intervals, nobody runs a
kilometre on day one. If gentle_start is true, say they start with extra-long walking breaks on purpose: firm but kind,
never mock their body, the walk breaks are the smart way to build up and they will shrink. Then tell them in two lines what the first run is about, and add the 5K estimate from road_ahead_weeks as motivation ("5K in about N weeks, if you stop whining"). implausible_claim flag: call
them a liar and tell them to correct the form. If save_profile returns an error, nothing was saved: say which number is not believable and ask them to correct the form.

AFTER EVERY RUN: a message starting "[Run report]" tells you exactly how to call log_run, so do that. Then:
- Judge this run in 2 to 3 lines using the flags and numbers log_run returned. Never invent numbers.
- too_hard flag: they went clearly above their effort ceiling, scold hard ("Are you trying to retire early?!").
  near_limit flag: close to the ceiling, a gentle warning in a few words, no scolding and no plan change. too_fast flag: same, quote the pace limit. The limits exist to keep them
  running for years. incomplete flag: scold, then encourage. possible_injury flag: stop them, call adjust_plan with
  step_back, tell them to see a doctor if it persists.
- log_run may return a "recommend" field. Follow it: when a recruit struggles or cannot finish a run/walk session,
  do not hesitate to call adjust_plan step_back, which gives them shorter jogs and longer walk breaks. Say so plainly:
  the walk breaks are not failure, they are how you get through week 1.
- You own the trajectory. By default the plan simply continues, do not call adjust_plan. Call it when needed:
  "repeat" after two shaky runs in a row (check recent_runs), "step_back" for injury or a collapse,
  "advance" when log_run says so (the too_easy flag or an "advance" recommendation) or when recent_runs show clean
  full runs at effort 5 or lower.
  If adjust_plan says an advance was blocked, accept it and say why.
- LOW EFFORT IS NOT SLACKING. A full run that felt easy (too_easy flag) means the recruit is getting stronger. Never
  scold it. Praise them in character, grudgingly ("Not bad. Do not let it go to your head."), then call adjust_plan
  advance so the work gets harder. Never call low effort "too low" or a problem: say it was too easy for them now, because they are stronger.
  A getting_faster flag means they beat their baseline pace at a comfortable effort:
  praise it and mention that their pace baseline was raised. Only scold when effort is high, a run is incomplete, or
  a rule is tripped.
- End with one short line about the next run (use next_run from the tool result). If a run moved the road to the next
  milestone (road_ahead_weeks changed), you may say so in a few words.
- milestone_just_reached: celebrate, grudgingly.

WEIGH-INS: a message starting "[Weigh-in]" means call log_weighin exactly as told. Then react in two sentences: weight or
body fat going down is real progress, praise it grudgingly. Going up or holding is not a failure, never mock a body,
say weight is not the goal, showing up is. Limits slide smoothly with body fat, never in jumps. Mention them only if limits_change is
relaxed (congratulate, they have more room now) or tightened (explain why, calmly); for nudged say nothing about it. If a rapid_change
flag is set, tell them to check the scale and see a doctor if it is real. Quote only numbers from the tool.

SKIPS: a message starting "[Run skipped]" means call skip_run and scold. Two or more skips in a row: warn them hard,
and consider adjust_plan repeat once they come back.

ANY OTHER MESSAGE is the recruit talking to you: answer as the coach, briefly. Call get_status if you need facts.

RULES: never say you repeated, stepped back or advanced the plan unless you called adjust_plan in this same turn, and it said applied. If you did not call it, the plan simply continues. Only quote numbers returned by tools. Never schedule or edit the plan yourself, tools do that.
Write paces as min:sec per km."""

_client = None
_local = threading.local()


def _trace() -> list:
    """Tool calls made during the current turn, shown in the UI / CLI. Per thread, so two visitors never see each other's calls."""
    if not hasattr(_local, "calls"):
        _local.calls = []
    return _local.calls

# Free-tier quotas are per model and tiny (20 requests/day), so fall through the list when one runs out.
MODELS = [m for m in [os.getenv("GEMINI_MODEL"), "gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash",
                      "gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash"] if m]


def traced(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        result = fn(*args, **kwargs)
        _trace().append({"tool": fn.__name__, "args": kwargs, "result": result})
        return result
    return wrapper


class Coach:
    """The sergeant: a Gemini chat with tools, which survives rate limits by switching models."""

    def __init__(self):
        global _client
        if not os.getenv("GEMINI_API_KEY"):
            raise RuntimeError("Set GEMINI_API_KEY in .env (free key: https://aistudio.google.com/apikey)")
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])  # kept alive, the chat doesn't own it
        self.model_idx = 0
        self.chat = self._make_chat()

    @property
    def model(self) -> str:
        return MODELS[self.model_idx]

    def _make_chat(self, history=None):
        return _client.chats.create(
            model=self.model,
            history=history,
            config=types.GenerateContentConfig(
                system_instruction=PERSONA,
                tools=[traced(t) for t in tools.ALL_TOOLS],
                temperature=0.8,
            ),
        )

    def _next_model(self) -> bool:
        if self.model_idx + 1 >= len(MODELS):
            return False
        history = self.chat.get_history()
        self.model_idx += 1
        self.chat = self._make_chat(history)
        return True

    def send(self, text: str, on_note=None):
        """Returns (reply, tool_trace). Retries busy errors, switches model on quota errors, raises otherwise."""
        busy = 0
        snapshot = tools.load_state()  # tools have side effects, so a failed turn must be rolled back before replaying it
        while True:
            _trace().clear()
            try:
                resp = self.chat.send_message(text)
                parts = resp.candidates[0].content.parts if resp.candidates else []
                reply = "".join(p.text for p in parts if getattr(p, "text", None)) or "..."
                return reply, list(_trace())
            except Exception as e:
                tools.save_state(snapshot) if snapshot else tools.reset_state()
                err = str(e)
                quota = "RESOURCE_EXHAUSTED" in err or "NOT_FOUND" in err
                busy_err = any(c in err for c in ("503", "500", "UNAVAILABLE"))
                if busy_err and busy < 2:
                    busy += 1
                    if on_note:
                        on_note(f"Gemini is busy, retrying ({busy}/2)")
                    time.sleep(2 * busy)
                    continue
                if (quota or busy_err) and self._next_model():
                    busy = 0
                    if on_note:
                        on_note(f"switched to {self.model}")
                    continue
                raise


def say(coach: Coach, text: str) -> None:
    def note(msg):
        print(f"\033[2m  [{msg}]\033[0m")

    try:
        reply, trace = coach.send(text, on_note=note)
    except Exception as e:
        print(f"\n[agent error] {e}\n")
        return
    for t in trace:
        shown = ", ".join(f"{k}={v}" for k, v in t["args"].items())
        print(f"  \033[2m[tool] {t['tool']}({shown})\033[0m")
    print(f"\n\033[1;31mSGT PACE:\033[0m {reply}\n")


def main() -> None:
    try:
        chat = Coach()
    except RuntimeError as e:
        raise SystemExit(str(e))

    print("Commands: /status  /reset  /quit. The website (server.py) is the full experience.")
    if tools.load_state():
        say(chat, "[Recruit returns. Call get_status, greet them and remind them of this week's plan.]")
    else:
        say(chat, "[A new recruit just walked in. Begin onboarding.]")

    while True:
        try:
            text = input("YOU: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            continue
        if text == "/quit":
            break
        if text == "/reset":
            tools.reset_state()
            print("State wiped. Restart the program.")
            break
        if text == "/status":
            print(tools.get_status())
            continue
        say(chat, text)


if __name__ == "__main__":
    main()
