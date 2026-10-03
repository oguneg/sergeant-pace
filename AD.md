# Sergeant Pace: 60-second ad

A self-playing page at `/ad` (file: `static/ad.html`, `ad.css`, `ad.js`). It is a deterministic timeline, so you can scrub it and re-take any moment.
Voiceover clips live in `static/ad/` (regenerate with `python ad_vo.py`; the sergeant is Orus, the recruit is Puck).

## Storyboard

| Time | Scene | On screen | Voiceover |
|---|---|---|---|
| 0:00 | The yes men | Cheerful coach-app notifications pop up ("Great job today, champ!") and each gets a red REJECTED stamp | "Are you tired of the yes men surrounding you?" |
| 0:05 | Yelled at | Slamming type: NEED TO BE / **YELLED AT** / TO GET MOTIVATED? over a shouting waveform | "Do you need to be yelled at to get motivated?" |
| 0:09 | The reveal | Hazard tape, then SERGEANT PACE slams in with the chevrons. "Couch to marathon. No excuses." | "If yes... have you met Sergeant Pace?" |
| 0:14 | Enlist | The real intake sheet: a cursor taps CANNOT RUN, the box is inked. Then the training order, the run timeline builds | "Can't run? Good. Nobody can on day one. We start with thirty seconds." |
| 0:22 | The run | The live run guide, time-lapsed: WARM UP, RUN, WALK, RUN with beeps and the progress needle | "Run! Walk! Run! Slow is the whole point, recruit." |
| 0:30 | The agent decides | The counseling sheet: facts typed, EFFORT TOO HIGH inked, the hazard plate drops, STEP BACK is stamped, old plan struck through, new plan typed. Caption: AN AI AGENT THAT RE-PLANS AFTER EVERY RUN | "Effort nine? Are you trying to retire early?! I just rewrote your whole plan." |
| 0:42 | Talk back | A recruit mumbles into the mic; the sergeant answers | recruit: "My knee hurts a little." / "Then see a doctor. Then get back here." |
| 0:50 | The ladder | 5K, 10K, HALF, MARATHON tiles get stamped QUALIFIED. NO EXCUSES. | "Five K. Ten K. Half. Full marathon. No excuses." |
| 0:57 | Close | Chevrons, SERGEANT PACE, "Fall in, recruit." ENLISTED stamp | "Sergeant Pace. Fall in." |

The screens use the app's real design and real agent wording (shortened). The recruit's data is made up for the ad.

## Recording it

1. Open `http://localhost:8000/ad` (start the server first), press **F** for full screen, **H** to hide the controls.
2. Press **Space** to play from the start. Use **R** to restart, **left/right** to scrub, **Space** to pause.
3. Record the screen with `Cmd+Shift+5`. **macOS does not capture sound in a screen recording.** Use the **Export audio** button (press **E**) to download the full mix as a WAV, then lay it under the video in iMovie, QuickTime or any editor. The audio is exactly 60 seconds and lines up with the page when both start at zero.
4. The stage is 16:9. On a 16:10 laptop screen there are thin bars top and bottom; crop in the editor.

## Changing it

All timings are constants at the top of `static/ad.js`. The voice lines are in `ad_vo.py`.
