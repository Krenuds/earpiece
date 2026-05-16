# musica phase-1 experiments

Throwaway scratch for validating the `/music` endpoint DSP before it gets
wired into `whisper-service` proper.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Run the synthetic tests

```bash
.venv/bin/python test_pitch.py
.venv/bin/python test_rhythm.py
```

These prove the libraries work on clean signals — they don't say anything
about real input.

## Run against a real sample

```bash
.venv/bin/python analyze_wav.py /path/to/humming.wav
```

Emits the proposed `/music` response shape:

```json
{
  "sr": 22050,
  "duration_s": ...,
  "rhythm": {"tempo_bpm": ..., "onsets_s": [...]},
  "notes": [{"onset_s": ..., "offset_s": ..., "pitch_hz": ..., "pitch_name": "A4", "confidence": ...}]
}
```
