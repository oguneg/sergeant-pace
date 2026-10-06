"""The sergeant's voice: Gemini text-to-speech out, Gemini transcription in."""
from __future__ import annotations

import array
import hashlib
import io
import json
import os
import wave
from pathlib import Path

from google import genai
from google.genai import types

import agent

CACHE = Path(os.getenv("SP_TTS_CACHE_DIR") or Path(__file__).parent / "tts_cache")
CACHE_MAX_MB = float(os.getenv("SP_TTS_CACHE_MB", "300"))  # stop caching new clips past this, so a public site cannot fill the disk
TTS_MODELS = [m for m in [os.getenv("GEMINI_TTS_MODEL"), "gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts",
                          "gemini-3.1-flash-tts-preview", "gemini-2.5-flash-preview-tts"] if m]
CHOICE_FILE = Path(__file__).parent / "voice_choice.json"
DEFAULT_VOICE, DEFAULT_STYLE = os.getenv("GEMINI_TTS_VOICE", "Orus"), "raspy"

# Gemini TTS reads a bare style instruction aloud. The director's-notes layout keeps the direction silent.
def _notes(style: str) -> str:
    return "### DIRECTOR'S NOTES\nStyle: " + style + "\n\n### TRANSCRIPT\n"

STYLES = {
    "raspy": ("Raspy drill sergeant", _notes("a furious, raspy, gravel-throated drill sergeant barking at a recruit. Hard, clipped delivery, shouting the emphatic words, zero warmth.")),
    "shout": ("Full scream", _notes("an enraged drill sergeant screaming at the top of his lungs, hoarse and shredded, every sentence a bark, no pauses for politeness.")),
    "cold": ("Cold and low", _notes("a cold, low, gravelly veteran drill sergeant. Quiet menace and contempt, short sentences, growling the emphatic words instead of shouting.")),
}

# Google's tone labels for the 30 prebuilt voices. "likely" marks the ones worth auditioning first for a gruff sergeant.
VOICES = [("Algenib", "Gravelly", True), ("Alnilam", "Firm", True), ("Orus", "Firm", True), ("Gacrux", "Mature", True),
          ("Charon", "Informative", True), ("Fenrir", "Excitable", True), ("Kore", "Firm", False), ("Rasalgethi", "Informative", False),
          ("Enceladus", "Breathy", False), ("Iapetus", "Clear", False), ("Schedar", "Even", False), ("Sadaltager", "Knowledgeable", False),
          ("Zephyr", "Bright", False), ("Puck", "Upbeat", False), ("Leda", "Youthful", False), ("Aoede", "Breezy", False),
          ("Callirhoe", "Easy-going", False), ("Autonoe", "Bright", False), ("Umbriel", "Easy-going", False), ("Algieba", "Smooth", False),
          ("Despina", "Smooth", False), ("Erinome", "Clear", False), ("Laomedeia", "Upbeat", False), ("Achernar", "Soft", False),
          ("Pulcherrima", "Forward", False), ("Achird", "Friendly", False), ("Zubenelgenubi", "Casual", False),
          ("Vindemiatrix", "Gentle", False), ("Sadachbia", "Lively", False), ("Sulafat", "Warm", False)]
VOICE_NAMES = {v for v, _, _ in VOICES}


def current() -> dict:
    """The voice and style the app speaks with, as chosen on the /voices page."""
    try:
        c = json.loads(CHOICE_FILE.read_text())
        if c.get("voice") in VOICE_NAMES and c.get("style") in STYLES:
            return {"voice": c["voice"], "style": c["style"]}
    except (OSError, ValueError):
        pass
    return {"voice": DEFAULT_VOICE, "style": DEFAULT_STYLE}


def choose(voice: str, style: str) -> dict:
    if voice not in VOICE_NAMES or style not in STYLES:
        raise ValueError("unknown voice or style")
    CHOICE_FILE.write_text(json.dumps({"voice": voice, "style": style}))
    return current()


# The API appends the same block of junk (about 125 ms) to every clip: that is the "radio static".
# It always starts with this exact sample sequence, so find it near the end and cut there.
_JUNK_HEAD = [12867, 16720, 6014, 0, 0, 32279, 30058, 25197]


def _clean(pcm: bytes, rate: int = 24000) -> bytes:
    """Cut the junk block off the end and fade the last 40 ms so the clip never clicks."""
    a = array.array("h")
    a.frombytes(pcm)
    n, k = len(a), len(_JUNK_HEAD)
    for i in range(max(0, n - 6000), n - k):
        if a[i] == _JUNK_HEAD[0] and list(a[i:i + k]) == _JUNK_HEAD:
            del a[i:]
            break
    fade = min(len(a), int(rate * 0.04))
    for i in range(fade):
        a[len(a) - fade + i] = int(a[len(a) - fade + i] * (1 - (i + 1) / fade))
    return a.tobytes()


def _repair_wav(wav: bytes) -> bytes:
    """Clean a clip that was cached before the cleanup existed."""
    with wave.open(io.BytesIO(wav)) as w:
        rate, pcm = w.getframerate(), w.readframes(w.getnframes())
    return _wav(_clean(pcm, rate), rate)


_client = None
_good_tts = 0  # index of the TTS model that last worked, tried first next time


def client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


def _wav(pcm: bytes, rate: int = 24000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def _cache_has_room() -> bool:
    try:
        return sum(f.stat().st_size for f in CACHE.iterdir()) < CACHE_MAX_MB * 1e6
    except OSError:
        return True


def speak(text: str, voice: str | None = None, style: str | None = None, notes: str | None = None) -> bytes:
    """Return WAV bytes of the sergeant barking `text`. Cached on disk so a take is only paid for once."""
    global _good_tts
    cur = current()
    voice, style = voice or cur["voice"], style or cur["style"]
    if voice not in VOICE_NAMES or style not in STYLES:
        raise ValueError("unknown voice or style")
    notes = notes or STYLES[style][1]  # a custom direction overrides the preset (used for the ad's recruit line)
    key = hashlib.sha1(f"{voice}|{notes}|{text}".encode()).hexdigest()
    path = CACHE / f"{key}.wav"
    if path.exists() and path.stat().st_size > 1000:  # ignore empty or truncated cache files
        return path.read_bytes()
    config = types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice))))
    order = TTS_MODELS[_good_tts:] + TTS_MODELS[:_good_tts]
    last = None
    for model in order:
        try:
            resp = client().models.generate_content(model=model, contents=notes + text, config=config)
            part = resp.candidates[0].content.parts[0].inline_data
            rate = 24000
            if part.mime_type and "rate=" in part.mime_type:
                rate = int(part.mime_type.split("rate=")[1].split(";")[0])
            wav = _wav(_clean(part.data, rate), rate)
            CACHE.mkdir(parents=True, exist_ok=True)
            if _cache_has_room():
                path.write_bytes(wav)
            _good_tts = TTS_MODELS.index(model)
            return wav
        except Exception as e:  # quota, unknown model, no audio returned: try the next one
            last = e
    raise last


def transcribe(data: bytes, mime: str = "audio/wav") -> str:
    """Turn a spoken reply into text."""
    prompt = "Transcribe this audio exactly as spoken. Output only the transcript, nothing else. If it is silent, output nothing."
    last = None
    for model in agent.MODELS:
        try:
            resp = client().models.generate_content(
                model=model, contents=[types.Part.from_bytes(data=data, mime_type=mime), prompt])
            parts = resp.candidates[0].content.parts if resp.candidates else []
            return "".join(p.text for p in parts if getattr(p, "text", None)).strip()
        except Exception as e:
            last = e
    raise last
