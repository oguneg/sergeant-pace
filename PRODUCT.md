# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Couch-to-marathon beginners. Mostly people who cannot run yet, plus beginners who can already run a bit and want to go longer. They use it between and around their runs, often on a phone, and report each run right after finishing it.

## Product Purpose

Sergeant Pace is a running coach agent. A recruit fills in a short intake (age, weight, height, body fat, longest recent run and pace), and the sergeant builds a training program that takes them from couch to 5K, 10K, half marathon and marathon milestones. After every run the recruit reports what happened, the sergeant judges that run, and the agent steers the trajectory of the upcoming runs (continue, repeat a level, step back, or advance). Success is a recruit who keeps showing up and finishes each milestone without getting hurt.

## Positioning

An agent, not a static plan: it re-plans after every single run from what the recruit actually did, and its safety limits are enforced in code rather than left to the model's judgment. Delivered in a tough-love drill sergeant voice.

## Operating Context

- Status: hackathon demo tonight (live demo, one local recruit, simulated Strava-style run data). May grow later. Real Strava import is the stated next step.
- Beginners start with a run/walk interval program (first run: 6 x 1 min run + 1 min walk), then move onto the km ladder 5K, 10K, 21K, 42K.
- 3 runs a week, shown as Week N, Day 1 to 3 (no weekday names). The plan always shows the next two weeks.
- Early interval sessions cannot be reported as km or minutes. Reporting is by intervals completed (or minutes run non-stop for timed runs) plus a 1 to 10 effort rating. Distance and time are asked only for km runs.
- The recruit reports one run at a time, never in weekly batches.

## Capabilities and Constraints

- Agent tools: save_profile, get_status, log_run, skip_run, adjust_plan. Plan numbers, paces and limits come from code and tool results; the model never invents them.
- Safety guardrails live in code. Pace and effort limits are stricter for high-risk profiles (body fat 30% or more, or age 55 or more). Advancing is blocked after a bad run or less than 3 runs after the last advance. Pain notes trigger a stop-and-see-a-doctor response.
- Runs on Flask with a single static page. One shared conversation, one recruit per server.
- Model: Gemini, on a free-tier key with tiny per-model daily quotas, so the agent falls through a list of models. Real Strava data is not connected.

## Brand Commitments

- Name: Sergeant Pace. A helmet emoji is the only avatar; no logo or other brand assets exist yet.
- Voice: tough-love drill sergeant. Shouty, funny, roasts you ("Are you trying to retire early?!"), but never cruel about bodies and never puts anyone in danger.

## Evidence on Hand

No real users, testimonials, or Strava data exist. Run data in the demo is simulated. Do not fabricate user counts, results, or endorsements.

## Product Principles

1. The next run is the focus. Everything else (ladder, upcoming weeks, history, chat) sits behind a button.
2. One thing per screen: never present the recruit with an information dump. Requested explicitly by the user during this build.
3. Safety is a rule in code, not a tone in a prompt.
4. The agent owns the trajectory; the recruit only reports what happened.
5. Beginners are never asked for numbers they cannot know (km or minutes of a run/walk session).
