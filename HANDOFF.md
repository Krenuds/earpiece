# Handoff - voice modes (Dreadnought filter)

Last updated 2026-10-03.

## Goal

A remotely switchable voice mode on piper-service. Flip one HTTP call to `dreadnought` (or `shodan`, `off`) and every `/tts` comes back processed through a robot-voice filter, until switched back. Per-request override allowed. Self-contained in the piper container.

## Decided

- Voice stays lessac (`en_US-lessac-medium`). The robot sound comes from post-processing, not a different voice or a formant synth.
- Filter engine is our Rust app shodan-voice (GitHub `shodan-voice`, local clone `~/shodan-voice`). It is a patchbay of modules behind a `Module` trait, with a deterministic offline WAV render path already.
- Reuse via a Cargo workspace split in shodan-voice: `shodan-core` (engine, DSP, modules, presets, no GUI or device I/O) + desktop app + `shodan-render` (headless, WAV on stdin/stdout). Earpiece pulls it as a Cargo git dependency pinned to a rev. No copy, no submodule.
- The headless binary ships inside the piper image (multi-stage Docker build). Piper pipes the WAV through it **before** the Opus encode. No new container or port.
- Mode lives in piper and persists. Presets are files in a mounted folder so knobs can be tweaked without a rebuild.

## State

- shodan-voice: workspace split merged and pushed to `master`. `shodan-render` matches the old `--render` byte for byte via files and stdin/stdout.
- piper: `/mode` (GET/POST), persisted active mode, per-request `mode`, `speed` (now wired to `length_scale`) and `noise_scale` are live on 9001. Mode files live in `piper-service/voicemodes/`, state in `~/services/data/piper/state`. A missing or failing render falls back to the dry voice. `dreadnought.json` only sets piper knobs so far. Mode is `off`.
- whisper: now runs `large-v3-turbo` (was `small`), about 0.5 s per average sentence on the 2080.
- Host: only `docker-compose` (v1 binary) is installed, not the `docker compose` plugin.

## Dreadnought sound profile

Measured on 232 clean DoW2 Retribution Dreadnought lines vs lessac (`refs/dreadnought/`, `an2.py`, venv in `.venv`; audio gitignored):

- Pitch ~96 Hz vs lessac ~191 Hz: about one octave down.
- Monotone: 2.6 semitone spread vs lessac 5.2.
- Huge sub-bass: ~1/3 of energy below 100 Hz (lessac: almost none). Peak near 130 Hz.
- Full-range, not radio band-passed. Highs stronger and ~10x noisier than lessac: grit/distortion.
- Weak hint of a ~2.6 ms comb (metal resonance). Unconfirmed.

A Python prototype (`refs/dreadnought/dreadnought_proto.wav`) landed "in the ballpark": pitch -10 st, sub layer at -22 st low-passed 160 Hz, 2.6 ms comb at 0.5, tanh drive x3, high-pass 60 Hz, 120 ms noise-burst steel-room reverb at 0.15.

## Next

1. New shodan-core modules for Dreadnought: pitch-down, sub layer, drive, comb resonance, short reverb. Tune against the DoW2 reference.
2. Piper: bake `shodan-render` into the image (multi-stage build) and add a `shodan` block to `voicemodes/dreadnought.json`.
3. Tuning loop snapshots ("go back two"), not built yet.

## Toji side

- No Toji changes needed. toji2 already POSTs every line to piper `/tts` with `format: opus`, so a piper-side mode applies transparently. Switching is a curl to the mode endpoint from the session.
- Mode is global: every piper consumer (toji2, toji3, anything on 9001) gets it. Accepted.
- Name it "voice mode". toji2 already has "voice filter" (`voice_filter_enabled`, `/filter`, `set_voice_filter`), which is the wake-word keyword filter.

## Tuning loop (voice-driven)

Travis tunes by voice from a live session; Toji's own replies are the test clips.

- Piper re-reads the active preset on every request: edits land with no restart.
- Each tweak saves a numbered snapshot so "go back two" works. Retention policy undecided; settle while building.
- "Voice off" always flips mode to off, so a broken voice can't lock him out.

## Open

- Should lessac stay recognizable under the effect, or vanish? Undecided.
- Space Marine 2 Dreadnought only exists as a mixed cutscene (needs Demucs + Whisper to isolate). Skipped for now.
