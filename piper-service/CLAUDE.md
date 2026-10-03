# piper-service

Piper-TTS wrapped in FastAPI. Text in, audio out. CPU-only.

## Container

- Built from `Dockerfile` (multi-stage, `python:3.11-slim`, non-root user `piper` uid 1001).
- Container name: `piper-service`, image: `piper-service-piper-service`.
- Port `9001` exposed.
- Audio backend: **PyAV** (`av==17.0.1`) handles WAV→Opus. No ffmpeg.

## Endpoints

| Method | Path | Notes |
|---|---|---|
| POST | `/tts` | `{text, voice?, speed?, noise_scale?, mode?, format?}`. `format` = `wav` \| `opus` (Opus = Ogg-Opus 48 kHz stereo 64 kbps `application=voip`). `speed` and `noise_scale` override the mode. |
| GET | `/mode` | `{mode, available}`. |
| POST | `/mode` | `{mode}`. Sets the active voice mode for every `/tts`; persists across restarts. `off` is always valid. |
| GET | `/voices` | Lists `EXTENDED_VOICE_CATALOG` from `config.py` with on-disk availability. |
| GET | `/health` | `{status, voice_models_loaded, default_voice, models_directory}`. |
| POST | `/download-voice` | Schedules a background HF download. **Errors in the background task are silently swallowed** — check logs to confirm. |
| GET | `/docs` | FastAPI Swagger UI. |

## Config (env vars read by `config.py`)

| Var | Default | Notes |
|---|---|---|
| `PIPER_HOST` | `0.0.0.0` | |
| `PIPER_PORT` | `9001` | |
| `PIPER_MODELS_DIR` | `/app/models/piper` | |
| `PIPER_DEFAULT_VOICE` | `en_US-lessac-low` (`-medium` in compose) | Pre-loaded at startup. |
| `PIPER_MAX_TEXT_LENGTH` | `10000` | Loaded but shadowed by Pydantic `max_length=10000` — see ROADMAP. |
| `PIPER_VOICE_MODES_DIR` | `voicemodes` | Mode files, mounted read-only from `./voicemodes`. |
| `PIPER_STATE_DIR` | `state` | Holds `active_mode`. Mounted from `~/services/data/piper/state` (uid 1001). |
| `PIPER_SHODAN_RENDER` | `shodan-render` | Filter binary for modes with a `shodan` block. |
| `LOG_LEVEL` | `INFO` | |
| `PIPER_LOG_FILE` | `/app/logs/piper-service.log` | |

## Voice modes

One `voicemodes/<name>.json` per mode, re-read on every request so edits land without a restart:

```json
{
  "piper": { "length_scale": 1.15, "noise_scale": 0.3, "noise_w": 0.8 },
  "shodan": { "preset": "ss1", "seed": 1, "rack": "id,id", "set": { "knob": 0.5 } }
}
```

Both blocks are optional. `shodan` pipes the WAV through `shodan-render` before the Opus encode. If the render fails, the dry voice is sent and the error is logged.

## Build / run / test

```bash
cd piper-service
docker compose up -d --build
curl -s localhost:9001/health | jq
curl -sX POST localhost:9001/tts \
  -H 'content-type: application/json' \
  -d '{"text":"hello","format":"opus"}' --output /tmp/t.ogg
docker compose logs -f
tail -f ../logs/piper-service.log
```

## Voices / models

- Catalog: `config.py::EXTENDED_VOICE_CATALOG` (en_US, en_GB, es_ES, fr_FR, de_DE — mix of low/medium qualities).
- Default voice `.onnx` + `.onnx.json` baked into the image **and** present on the host bind-mount at `~/services/data/piper/models`.
- Add a voice: `POST /download-voice` with a catalog key (e.g. `en_GB-alan-medium`). Pulls from `huggingface.co/rhasspy/piper-voices/...`.
- Loaded models live in an in-memory dict with **no eviction** — restart the container to reclaim memory if you've loaded many voices.

## Troubleshooting

- Unhealthy after build: check `docker compose logs` and `../logs/piper-service.log`. Healthcheck `start_period` is 45s.
- "Voice not found in catalog": voice key not in `EXTENDED_VOICE_CATALOG` — add to `config.py` or pick one from `GET /voices`.
- Opus output sample rate: `wav_to_opus()` force-resamples to 48 kHz stereo regardless of input.
- 500 from `/tts`: usually a missing `.onnx` file the download fallback couldn't fetch. Check network and that the models bind-mount is writable by uid 1001.
- Memory growth over time: every distinct voice you've requested stays loaded for the container's lifetime.

## Known cruft (deferred — see repo `ROADMAP.md`)

- `/download-voice` errors are swallowed by the BackgroundTask runner.
- `PIPER_MAX_TEXT_LENGTH` is loaded but ignored (Pydantic cap shadows it).
- Redundant model-existence check in `/download-voice` vs `download_voice_model()`.
