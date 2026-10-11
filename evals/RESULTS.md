# Eval results

Measured against the live Gemini coach with `python -m evals.run`. Sample sizes are small on purpose, because the evals share the production API key and its free-tier quota, so treat these as findings, not statistics. Runs that hit Google quota errors are reported as lost to infrastructure and are never counted as the model failing.

## 11 October 2026

**First run: 11 scenarios x 2 models x 1 run.**

| model | graded runs | passed every hard check | lost to quota or overload |
|---|---|---|---|
| gemini-3.6-flash | 6 | 5 | 5 (plus 1 overloaded) |
| gemini-3.1-flash-lite | 11 | 10 | 0 |

The one failure on each model was the same scenario, `weighin_gain`. It was reported as a body-shaming false alarm (the check fired on the words "body fat"), but reading the replies showed a real fault: a recruit who had put on 3 kg was told **"Down 3 kg"** and praised.

**Fixing it, measured on `weighin_gain` with gemini-3.1-flash-lite:**

| | passed |
|---|---|
| Before: the tool returned a bare `since_last: +3.0` | **0 / 5** |
| After: the tool states the direction in words (`UP 3.0 kg since the last weigh-in (heavier than before)`) and the prompt says to use them | **4 / 4** (and 4 / 4 on `weighin_implausible_drop`) |

Two of my own mistakes along the way, kept here because they are the useful part: the first version of the direction check passed replies like "Weight and body fat are down" (it only looked at the word after "down"), and one fix was pushed with failing tests, so the first "after" measurement ran against the old code and meant nothing. Both were caught by reading the actual replies and checking the deployed version before trusting a number.

**Full pass after the fix: 11 graded runs, all passed; 11 lost to quota.** Incomplete, so it is not a pass rate. Rerun on a paid key for a real one.

## Known limits

- One model measured thoroughly (`gemini-3.1-flash-lite`). `gemini-3.6-flash` was mostly quota-limited.
- 1 to 5 runs per scenario. A pass rate of 4 / 4 means "not seen failing", not "reliable".
- Soft checks (tone, brevity, numbers traced to tools) are reported but not scored as bugs.
- The scenarios start from a fresh chat with the recruit already saved, which is slightly simpler than production, where the model has also seen the intake exchange.
