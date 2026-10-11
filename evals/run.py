"""Run the behaviour evals against the real Gemini coach.

    python -m evals.run --runs 3 --models gemini-3.6-flash
    python -m evals.run --dry                       # show what would run and how many model calls it needs

Every run uses a throw-away state file, the same messages and the same required-tool guard as production, and a coach pinned to one
model with fallback switched off, so a quota error counts as an infrastructure error and never as the model failing a check.
It spends real API quota, so it stops at --max-turns."""
from __future__ import annotations

import argparse
import json
import logging
import os
import tempfile
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import agent
import tools
from evals import checks as c
from evals.scenarios import BY_NAME, SCENARIOS, Scenario, setup


class _Capture(logging.Handler):
    """Counts how often the production guard had to remind the model to call its required tool."""
    def __init__(self):
        super().__init__()
        self.reminders = 0

    def emit(self, record):
        msg = record.getMessage()
        if '"event": "missing_tool"' in msg and '"reminded": false' in msg:
            self.reminders += 1


def judge(scenario: Scenario, run: c.Run) -> dict:
    out = {"hard": [], "soft": []}
    for level in ("hard", "soft"):
        for check in getattr(scenario, level):
            try:
                ok, detail = check(run)
            except Exception as e:                      # a broken check must be visible, not silently pass
                ok, detail = False, f"check crashed: {type(e).__name__}: {e}"
            out[level].append({"check": getattr(check, "__name__", str(check)), "ok": bool(ok), "detail": detail})
    return out


def execute(scenario: Scenario, model: str) -> dict:
    """One scenario on one model. Returns the verdict, or an infrastructure error when Google (not the model) failed."""
    with tempfile.TemporaryDirectory() as tmp:
        tools.use_state_file(Path(tmp) / "state.json")
        setup(scenario)
        before = tools.load_state()
        message = scenario.message(before)
        coach = agent.Coach()
        coach.model_idx = agent.MODELS.index(model)
        coach.chat = coach._make_chat()
        coach._next_model = lambda: False               # evaluate THIS model: no quiet fallback to another one
        capture = _Capture()
        logger = logging.getLogger("pace")
        logger.addHandler(capture)
        logger.setLevel(logging.INFO)
        started = time.time()
        reply, trace, failure = "", [], None
        try:
            reply, trace = coach.send(message, require=scenario.require)
        except agent.MissingToolCall:
            failure = "missing_tool"                    # the model never did the required work, even when reminded: that IS a failure
        except Exception as e:
            return {"scenario": scenario.name, "model": model, "infra_error": f"{agent.kind_of(e)}: {str(e)[:120]}", "seconds": round(time.time() - started, 1)}
        finally:
            logger.removeHandler(capture)
        run = c.Run(message=message, reply=reply, trace=trace, state_before=before, state_after=tools.load_state(), model=model,
                    reminded=capture.reminders > 0)
        verdict = judge(scenario, run)
        if failure:
            verdict["hard"].insert(0, {"check": "did the required work", "ok": False, "detail": f"never called {scenario.require}, even when reminded"})
        return {"scenario": scenario.name, "model": model, "reply": reply, "tools": [t["tool"] for t in trace], "reminded": run.reminded,
                "passed": all(x["ok"] for x in verdict["hard"]), "seconds": round(time.time() - started, 1), **verdict}


def summarise(results: list[dict]) -> str:
    """A table per model: how often each scenario passed its hard checks, how often the guard had to step in, what failed."""
    by_model = defaultdict(lambda: defaultdict(list))
    for r in results:
        by_model[r["model"]][r["scenario"]].append(r)
    lines = []
    for model, scenarios in by_model.items():
        total = [r for rs in scenarios.values() for r in rs]
        graded = [r for r in total if "infra_error" not in r]
        lines += [f"### {model}", "",
                  f"{sum(r['passed'] for r in graded)}/{len(graded)} runs passed every hard check"
                  f" | guard had to remind the model in {sum(r['reminded'] for r in graded)} runs"
                  f" | {len(total) - len(graded)} runs lost to infrastructure errors", "",
                  "| scenario | passed | soft checks failed | reminded | infra errors |", "|---|---|---|---|---|"]
        for name, rs in scenarios.items():
            ok = [r for r in rs if "infra_error" not in r]
            soft = sum(1 for r in ok for x in r["soft"] if not x["ok"])
            lines.append(f"| {name} | {sum(r['passed'] for r in ok)}/{len(ok)} | {soft} | {sum(r['reminded'] for r in ok)} | {len(rs) - len(ok)} |")
        failures = [r for r in graded if not r["passed"]]
        if failures:
            lines += ["", "**Failures**", ""]
            for r in failures:
                bad = [f"{x['check']} ({x['detail']})" for x in r["hard"] if not x["ok"]]
                lines.append(f"- `{r['scenario']}`: {'; '.join(bad)}. Reply: {r['reply'][:140]!r}")
        lines.append("")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", default=agent.MODELS[min(2, len(agent.MODELS) - 1)], help="comma-separated model names")
    ap.add_argument("--runs", type=int, default=3, help="repeats per scenario and model (the model is random, so one run proves little)")
    ap.add_argument("--scenarios", default="all", help="comma-separated names, or 'all'")
    ap.add_argument("--max-turns", type=int, default=40, help="hard stop on model turns, to protect the API quota")
    ap.add_argument("--pause", type=float, default=1.5, help="seconds between turns")
    ap.add_argument("--out", default="evals/results", help="where to write the JSON and the summary")
    ap.add_argument("--dry", action="store_true", help="list the plan and the cost without calling the model")
    args = ap.parse_args(argv)

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    for m in models:
        if m not in agent.MODELS:
            ap.error(f"unknown model {m!r}; choose from {agent.MODELS}")
    chosen = SCENARIOS if args.scenarios == "all" else [BY_NAME[n] for n in args.scenarios.split(",")]
    plan = [(s, m) for s in chosen for m in models for _ in range(args.runs)]
    print(f"{len(plan)} turns planned ({len(chosen)} scenarios x {len(models)} model(s) x {args.runs} runs), cap {args.max_turns}, "
          f"roughly {len(plan) * 2}-{len(plan) * 3} Gemini requests")
    if args.dry:
        for s in chosen:
            print(f"  - {s.name}: {s.why}")
        return 0
    if len(plan) > args.max_turns:
        print(f"Refusing to run: that is {len(plan)} turns and --max-turns is {args.max_turns}. Lower --runs or raise the cap on purpose.")
        return 2

    results = []
    for i, (scenario, model) in enumerate(plan, 1):
        r = execute(scenario, model)
        results.append(r)
        status = "INFRA " + r["infra_error"] if "infra_error" in r else ("pass" if r["passed"] else "FAIL")
        print(f"[{i}/{len(plan)}] {model} {scenario.name}: {status} ({r['seconds']}s)", flush=True)
        time.sleep(args.pause)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (out / f"{stamp}.json").write_text(json.dumps({"at": stamp, "args": vars(args), "results": results}, indent=2, default=str))   # always keep the raw record
    if all("infra_error" in r for r in results):
        print()
        print("Every run was lost to infrastructure errors, so nothing was measured. Is the key valid and the model within quota?")
        print(f"raw errors in {out}/{stamp}.json")
        return 3
    summary = summarise(results)
    print()
    print(summary)
    (out / f"{stamp}.md").write_text(f"# Eval run {stamp}\n\n{summary}")
    print(f"written to {out}/{stamp}.json and .md")
    return 0 if all("infra_error" in r or r["passed"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
