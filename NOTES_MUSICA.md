# musica — proposed extension

Rough notes. Updated 2026-05-16 after a design pass.

## Context

`musica` is a new workspace aimed at being the first hands-free DAW: Travis describes / hums / beatboxes a song from the truck, the system turns that into structured musical data, plays it back, and iterates conversationally.

The hard constraint: voice input to Toji is currently one-way lossy — Discord Opus → whisper-service → **text**. Pitch, timing, and timbre are discarded at the STT step. For a DAW, that signal needs to survive.

## Direction (current pass)

**Add a `/music` endpoint to `whisper-service`** rather than spinning up a third microservice.

- Single upload, single response. Returns whisper text **and** musical analysis together.
- The expectation is the consumer always wants both — text + notes + rhythm — so splitting them across two services means two uploads of the same audio for one logical call. Not worth it.
- Same multipart-file-upload shape as `/asr`. No streaming, no PCM-over-the-wire — the client POSTs a file, the service does its work, JSON comes back.

## Implementation shape

Pure DSP, no inference. This is the big simplification from the previous draft.

- **Pitch:** `librosa.pyin` (monophonic, classical algorithm, milliseconds on CPU).
- **Onsets / rhythm:** `librosa.onset.onset_detect` + `librosa.beat` for tempo. `aubio` is the alternative if librosa's beat tracking is too sloppy on beatboxed input.
- **Key detection:** out of scope for v1. Derivable from the note sequence later if we want it.
- No GPU. No model files. No HuggingFace cache. Just numpy and a couple of pip installs.

Reasoning: neural pitch trackers (CREPE / RMVPE / FCPE) and unified models (STARS, ROSVOT) exist and are impressive, but they're aimed at noisy / polyphonic / vibrato-heavy input. For a single voice singing or beatboxing into a mic, pYIN is genuinely fine and an order of magnitude cheaper to run and operate.

Prior art was researched — STARS (arXiv 2507.06670) is the closest unified model and worth revisiting if v1 isn't accurate enough, but it's batch-only and clean-vocals-trained.

## Open questions (unresolved — next session)

1. **Output schema.** No standard exists. Working assumption: note events as `{onset, offset, pitch_hz, pitch_name, confidence}` plus a parallel rhythm block `{onsets[], tempo_bpm}` plus the existing whisper segments/words. STARS-style "words point at note indices" alignment is appealing but probably overkill for v1.
2. **How toji2 consumes this.** This is the bigger question and the real reason to checkpoint here. The `/music` endpoint is the easy part — wiring it into toji2's audio pipeline so a hum or a beatbox routes here instead of (or in parallel with) the normal `/asr` path is where the design work actually lives. Picking that up next session.
3. **Trigger model.** Does every voice chunk get music-analyzed, or is it gated by a wake phrase / mode? Tied to question 2.

## Not deciding yet

- Language for the `musica` workspace app itself.
- Whether `/music` ever needs a streaming variant. Probably not for v1.

This file is a scratchpad — promote anything that survives the next pass into the proper docs.
