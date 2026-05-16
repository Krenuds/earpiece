"""Phase 1 DSP analyzer for the `musica` experiment.

Pure-DSP, no models. Given a mono audio buffer + sample rate, returns a dict
shaped roughly like the proposed /music JSON response.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import librosa
import numpy as np


PYIN_FMIN = librosa.note_to_hz("C2")
PYIN_FMAX = librosa.note_to_hz("C5")


@dataclass
class Note:
    onset_s: float
    offset_s: float
    pitch_hz: float
    pitch_name: str
    confidence: float


def _hz_to_name(hz: float) -> str:
    if not math.isfinite(hz) or hz <= 0:
        return ""
    return librosa.hz_to_note(hz)


def analyze(y: np.ndarray, sr: int) -> dict:
    if y.ndim > 1:
        y = librosa.to_mono(y)

    f0, voiced_flag, voiced_prob = librosa.pyin(
        y,
        sr=sr,
        fmin=PYIN_FMIN,
        fmax=PYIN_FMAX,
    )

    onset_frames = librosa.onset.onset_detect(y=y, sr=sr, units="frames")
    onset_times = librosa.frames_to_time(onset_frames, sr=sr).tolist()

    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    tempo_bpm = float(np.atleast_1d(tempo)[0])

    duration_s = float(len(y) / sr)
    notes = _group_notes(f0, voiced_flag, voiced_prob, sr, onset_times, duration_s)

    return {
        "sr": sr,
        "duration_s": duration_s,
        "rhythm": {
            "tempo_bpm": tempo_bpm,
            "onsets_s": onset_times,
        },
        "notes": [asdict(n) for n in notes],
    }


def _group_notes(
    f0: np.ndarray,
    voiced_flag: np.ndarray,
    voiced_prob: np.ndarray,
    sr: int,
    onset_times: list[float],
    duration_s: float,
) -> list[Note]:
    """Slice the pyin f0 track at each onset; emit a Note per slice with enough
    voiced content. Crude but adequate for phase 1 validation."""
    if len(f0) == 0:
        return []

    times = librosa.times_like(f0, sr=sr)
    boundaries = sorted(set([0.0] + list(onset_times) + [duration_s]))
    notes: list[Note] = []

    for start, end in zip(boundaries, boundaries[1:]):
        if end - start < 0.05:
            continue
        mask = (times >= start) & (times < end) & voiced_flag
        if mask.sum() < 3:
            continue
        voiced_fraction = mask.sum() / max(1, ((times >= start) & (times < end)).sum())
        if voiced_fraction < 0.5:
            continue
        pitches = f0[mask]
        confs = voiced_prob[mask]
        pitch_hz = float(np.nanmedian(pitches))
        conf = float(np.nanmean(confs))
        notes.append(
            Note(
                onset_s=round(start, 4),
                offset_s=round(end, 4),
                pitch_hz=round(pitch_hz, 3),
                pitch_name=_hz_to_name(pitch_hz),
                confidence=round(conf, 3),
            )
        )
    return notes
