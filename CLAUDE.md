# earpiece

Two Docker microservices for voice I/O, text-to-speech and speech-to-text, exposed as plain HTTP
APIs. Toji uses both, but they stay independent of any one consumer.

## Services

| Service | Role | Port | Hardware |
|---|---|---|---|
| `piper-service` | TTS: text to WAV or Ogg-Opus, switchable voice modes | 9001 | CPU only |
| `whisper-service` | STT: audio to text, json, srt or vtt (`large-v3-turbo`) | 9000 | NVIDIA GPU, CPU fallback |

Each service runs from its own directory with its own `docker-compose.yml`; there is no root
compose and there shouldn't be. Only the v1 `docker-compose` binary is installed, not the
`docker compose` plugin. Each service has its own `CLAUDE.md` for its config keys.

## Host paths

| Host path | Purpose |
|---|---|
| `./logs/` | Mounted into both containers as `/app/logs`, rotated logs (10MB x 5) |
| `~/services/data/piper/models` | Piper voice models (`.onnx` + `.json`) |
| `~/services/data/piper/state` | Persisted active voice mode |
| `piper-service/voicemodes/` | Voice mode files, mounted read-only; edit without a rebuild |
| `~/services/data/whisper/models` | HF cache for whisper models |

## Common operations

```bash
cd piper-service && docker-compose up -d --build   # ship code changes
cd piper-service && docker-compose restart
tail -f logs/piper-service.log logs/whisper-service.log
curl -s localhost:9001/health; curl -s localhost:9000/health
```

## Configuration

Config is the `environment:` block in each service's compose file. There is no live `.env`;
the `.env.example` files are reference only.

## Open work

- `HANDOFF.md`: voice modes (Dreadnought filter via shodan-render from `~/shodan-voice`), state
  and next steps.
- `ROADMAP_MUSICA.md`: the `/music` analyzer endpoint.
