# Sergeant Pace

An AI running coach with a drill sergeant's voice. A visitor enters age, weight, height, body fat and running history; Gemini (through tool calls) plans couch-to-marathon and re-plans after every run. Live at https://pace.ogun.se. Owner: Ogün Gündogdu (hello@ogun.se).

## Commands

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt   # macOS/Linux: .venv/bin/pip
.venv/Scripts/python -m pytest -q          # 175 tests, ~13 s, no API key and no network
.venv/Scripts/python server.py             # http://localhost:8000 (needs GEMINI_API_KEY in .env; dev mode keeps the /voices picker)
.venv/Scripts/python agent.py              # terminal version
```

## Map

- `tools.py`: **all rules and numbers.** Plan, limits, safety flags, the six tools the model can call. The model never writes a number.
- `agent.py`: Gemini chat, retry, model fallback, state rollback, background model probe, `require=` guarantee.
- `server.py`: Flask. Per-visitor sessions, rate limits, daily caps, availability status, privacy page, data export.
- `voice.py`: Gemini text-to-speech and transcription. `sim.py`: scenario generator used by the demo and the tests.
- `static/`: the UI (`app.js`, `app.css`) and `privacy.html`. `tests/`: everything runs against fakes.
- `private/` is git-ignored interview notes. Do not read them into public files, and never commit them.

## Rules that must not break

1. **The model talks, the code decides.** Limits, flags and plan changes live in `tools.py`. Do not move a rule into the prompt.
2. **Tools take no recruit argument.** The server pins one visitor's file per request (`tools.use_state_file`). Never let the model choose whose file it edits.
3. **Every action requires its tool call.** `Coach.send(..., require="log_run")`: a reply without the call is discarded, work is rolled back, the model is reminded once, then `MissingToolCall`. A weaker model really did say "I've stepped you back" without calling anything.
4. **Fail fast.** The Gemini client has no SDK retries and a 20 s timeout (the SDK default stalled visitors for minutes). The API rejects deadlines under 10 s. A whole turn is capped at 55 s.
5. **One shared Gemini client** for the process (per-conversation clients once killed each other's requests), a thread-local trace, and **one gunicorn worker on purpose**: sessions and limits live in memory.
6. **Public mode (`SP_PUBLIC=1`, set in the image):** no voice picker, no error details to the browser, no caller-chosen voice.
7. **Privacy.** Health data needs the consent tick box, which blocks the form before anything is sent. `/privacy` is generated from real settings and tests tie each promise to the code. Set `SP_GEMINI_PAID=1` **only** when the key is on a paid plan, because the notice then says Google does not train on it.

## Testing

- New rule or guardrail: add a test, then **break the code on purpose and confirm the test fails** (a test once read the cap from the module it was guarding).
- Tests use fake models and clients; never call the network. A test double for the coach must accept `on_note` and `require`.
- Keep the README's test count and numbers in sync with the code.

## Deploy

Push to `main` runs pytest in GitHub Actions, then SSHes to the VPS with a key restricted to `deploy/update.sh` (builds the image, swaps the container, waits for health). Site: https://pace.ogun.se/healthz. The server (debian@57.129.169.251, `~/sergeant-pace`, shared Caddy proxy) holds `.env` with the Gemini key. Never print, commit or log it. Pushing deploys, so push only when asked.

## Gotchas

- The Gemini free tier throttles the top models. At startup a background probe finds the fastest working model; the fallback list is `agent.MODELS`. Failures are logged as one JSON line per event (`turn`, `probe`, `missing_tool`) with a `kind`.
- `/api/state` carries `status` (daily budget spent, own allowance used, Google overloaded). The page shows a banner before the form.
- Bump `?v=` on `app.js` and `app.css` in `static/index.html` when you change them.
- Windows: use `.venv/Scripts/python`; Docker is not installed locally, the image builds on the server.
- Commit messages say why. Python 3.13; comments explain why, not what.
