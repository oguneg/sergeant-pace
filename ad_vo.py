"""Generate the voiceover clips for the ad into static/ad/ (run once; clips are cached by voice.py)."""
import io
import json
import wave
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
import voice  # noqa: E402

OUT = Path(__file__).parent / "static" / "ad"
RECRUIT_NOTES = ("### DIRECTOR'S NOTES\nStyle: a tired, sheepish, out-of-breath recruit mumbling an excuse, small and unsure.\n\n### TRANSCRIPT\n")

LINES = [  # id, text, voice, notes
    ("v1", "Are you tired of the yes men surrounding you?", "Orus", None),
    ("v2", "Do you need to be yelled at to get motivated?", "Orus", None),
    ("v3", "If yes... have you met Sergeant Pace?", "Orus", None),
    ("v4", "Can't run? Good. Nobody can on day one. We start with thirty seconds.", "Orus", None),
    ("v5", "Run! Walk! Run! Slow is the whole point, recruit.", "Orus", None),
    ("v6", "Effort nine? Are you trying to retire early?! I just rewrote your whole plan.", "Orus", None),
    ("v7", "My knee hurts a little.", "Puck", RECRUIT_NOTES),
    ("v8", "Then see a doctor. Then get back here.", "Orus", None),
    ("v9", "Five K. Ten K. Half. Full marathon. No excuses.", "Orus", None),
    ("v10", "Sergeant Pace. Fall in.", "Orus", None),
]

manifest = {}
for vid, text, vname, notes in LINES:
    wav = voice.speak(text, vname, "raspy", notes)
    (OUT / f"{vid}.wav").write_bytes(wav)
    with wave.open(io.BytesIO(wav)) as w:
        manifest[vid] = {"text": text, "duration": round(w.getnframes() / w.getframerate(), 2)}
    print(vid, manifest[vid]["duration"], "s", "-", text)
(OUT / "vo.json").write_text(json.dumps(manifest, indent=2))
print("total VO", round(sum(m["duration"] for m in manifest.values()), 1), "s")
