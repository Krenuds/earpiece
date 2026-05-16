"""CLI: analyze a WAV file and print the proposed /music JSON response.

Usage:
    .venv/bin/python analyze_wav.py path/to/audio.wav

The output is the same dict the /music endpoint would eventually return.
"""

from __future__ import annotations

import argparse
import json
import sys

import librosa

from analyzer import analyze


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the musica phase-1 analyzer on a WAV.")
    ap.add_argument("path", help="WAV file path")
    ap.add_argument("--sr", type=int, default=22050, help="target sample rate (default 22050)")
    args = ap.parse_args()

    y, sr = librosa.load(args.path, sr=args.sr, mono=True)
    result = analyze(y, sr)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
