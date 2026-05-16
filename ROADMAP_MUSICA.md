# musica — roadmap

Last updated 2026-05-16.

## Goal

Hum, sing, or beatbox a melody from the truck. Get back structured musical
data — notes with onsets, offsets, pitches. Phase 1 deliverable is a `/music`
endpoint on `whisper-service` that runs alongside `/asr`.

## What we've tested

| Approach | Result | Verdict |
|---|---|---|
| **pYIN (librosa)** | Clean pitch tracking on sung voice. `maryhadalittlelamb.wav` produced 9 stable pitch plateaus that closely match the singing. | **Works.** Keep. |
| **BasicPitch (Spotify, neural)** | Same Mary clip came back with 12 noisy notes for ~7 sung syllables. Designed for polyphonic music, not solo vocals. | **Wrong tool.** Drop. |
| **Onset-based note segmentation** | `librosa.onset.onset_detect` misfires on legato singing — merges syllables, fires spuriously on plosives. | **Wrong approach** for sung input. |
| **Synthetic smoke tests** | Sine tones tracked to under 1 cent. Click tracks recover tempo within ~3 BPM. | Library wiring is sound. |

## Open decision

How do we segment a clean pYIN pitch track into clean notes?

Leading candidate: walk the f0 series, round each frame to the nearest
semitone, find runs of stable values, emit one note per run. Untested. This
is the next experiment.

## Out of scope

Spoken input. Spoken counting doesn't sit on musical pitches — no transcriber
will recover melody from it. The DAW use case requires sung or hummed input.

## Phases

1. **Pitch-plateau segmenter.** Build it on top of the existing pYIN
   analyzer. Pass condition: at least 6 of 7 sung syllables of "Mary had a
   little lamb" come back as distinct notes with correct contour.
2. **Output schema.** Lock the JSON shape for note events plus rhythm block.
   Cheap to change now, expensive later.
3. **`/music` endpoint.** Wire the analyzer into `whisper-service` as a new
   route. Same multipart shape as `/asr`.
4. **Combined call.** Decide whether `/asr` and `/music` run in parallel
   server-side or stay separate and `toji2` fans out. Not a build step.
5. **`toji2` integration.** Trigger model (always-on versus gated) and
   pipeline wiring. This is the real open question.
6. **`musica` workspace app.** The consumer. Stack choice happens here.

## Current artifacts

- `whisper-service/experiments/musica/analyzer.py` — pYIN + onset/tempo
  analyzer (phase 1 scaffold).
- `whisper-service/experiments/musica/analyze_wav.py` — CLI runner used for
  testing against native audio.
- `whisper-service/experiments/musica/test_pitch.py`,
  `test_rhythm.py` — synthetic smoke tests.

`discord_attachments/` holds the WAV samples used during testing
(`maryhadalittlelamb.wav`, `1_2_3_4.wav`); gitignored.
