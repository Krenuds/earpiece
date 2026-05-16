"""Synthetic rhythm test — generate a click track at a known BPM, confirm
tempo and onset count come back."""

import numpy as np

from analyzer import analyze


def _click_track(bpm: float, sr: int, num_beats: int) -> np.ndarray:
    spb = 60.0 / bpm
    duration_s = num_beats * spb
    n = int(sr * duration_s)
    y = np.zeros(n, dtype=np.float32)
    click_len = int(0.01 * sr)
    envelope = np.exp(-np.linspace(0, 6, click_len)).astype(np.float32)
    noise = np.random.default_rng(0).standard_normal(click_len).astype(np.float32)
    click = envelope * noise * 0.8
    for i in range(num_beats):
        start = int(i * spb * sr)
        end = min(start + click_len, n)
        y[start:end] += click[: end - start]
    return y


def test_120_bpm():
    sr = 22050
    bpm = 120.0
    num_beats = 8
    y = _click_track(bpm, sr, num_beats)

    result = analyze(y, sr)
    tempo = result["rhythm"]["tempo_bpm"]
    onsets = result["rhythm"]["onsets_s"]
    print(f"  120 BPM click -> tempo {tempo:.2f}, onsets {len(onsets)}")

    assert abs(tempo - bpm) < 3, f"tempo off: got {tempo}, expected {bpm}"
    # librosa often misses the very first onset or merges adjacent — allow ±1
    assert abs(len(onsets) - num_beats) <= 1, \
        f"onset count off: got {len(onsets)}, expected {num_beats}"


def test_90_bpm():
    sr = 22050
    bpm = 90.0
    num_beats = 6
    y = _click_track(bpm, sr, num_beats)

    result = analyze(y, sr)
    tempo = result["rhythm"]["tempo_bpm"]
    onsets = result["rhythm"]["onsets_s"]
    print(f"  90 BPM click  -> tempo {tempo:.2f}, onsets {len(onsets)}")

    assert abs(tempo - bpm) < 3 or abs(tempo - 2 * bpm) < 3, \
        f"tempo not 90 or 180: got {tempo}"
    assert abs(len(onsets) - num_beats) <= 1, \
        f"onset count off: got {len(onsets)}, expected {num_beats}"


if __name__ == "__main__":
    test_120_bpm()
    print("ok: 120 BPM")
    test_90_bpm()
    print("ok: 90 BPM")
