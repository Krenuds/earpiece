"""Synthetic pitch test — generate a known sine, confirm pYIN tracks it."""

import math

import librosa
import numpy as np

from analyzer import analyze


def _sine(freq: float, sr: int, duration_s: float) -> np.ndarray:
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    return 0.5 * np.sin(2 * math.pi * freq * t).astype(np.float32)


def test_constant_pitch_a4():
    sr = 22050
    target_hz = 440.0
    y = _sine(target_hz, sr, 2.0)

    result = analyze(y, sr)

    notes = result["notes"]
    assert notes, "expected at least one note for a 2s sine"

    median_pitch = np.median([n["pitch_hz"] for n in notes])
    cents_off = 1200 * math.log2(median_pitch / target_hz)
    print(f"  A4 sine -> median {median_pitch:.2f} Hz ({cents_off:+.1f} cents)")
    assert abs(cents_off) < 10, f"pitch off by {cents_off:.1f} cents"

    expected_name = librosa.hz_to_note(target_hz)
    assert any(n["pitch_name"] == expected_name for n in notes), \
        f"no note labeled {expected_name}; got {[n['pitch_name'] for n in notes]}"


def test_two_pitch_glissando():
    """Half a second of A4, half a second of E5, jump in the middle."""
    sr = 22050
    y = np.concatenate([_sine(440.0, sr, 0.7), _sine(659.25, sr, 0.7)])

    result = analyze(y, sr)
    notes = result["notes"]
    pitches = [n["pitch_hz"] for n in notes]
    print(f"  A4->E5 step -> recovered pitches: {[round(p, 1) for p in pitches]}")

    assert any(abs(p - 440.0) < 10 for p in pitches), "missed A4"
    assert any(abs(p - 659.25) < 15 for p in pitches), "missed E5"


if __name__ == "__main__":
    test_constant_pitch_a4()
    print("ok: constant A4")
    test_two_pitch_glissando()
    print("ok: A4->E5 step")
