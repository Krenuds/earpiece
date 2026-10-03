"""
Piper TTS HTTP Service

A production-ready FastAPI service for text-to-speech using Piper TTS.
This service converts the embedded Piper client library into a RESTful HTTP API.
"""

import asyncio
import io
import json
import os
import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict, List, Any, Literal
import urllib.request
import wave
from contextlib import asynccontextmanager

import av

from fastapi import FastAPI, HTTPException, Response, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import piper
import uvicorn

from config import ServiceConfig, EXTENDED_VOICE_CATALOG, setup_logging


# Request/Response models
class TTSRequest(BaseModel):
    """Request model for text-to-speech generation."""
    text: str = Field(..., description="Text to convert to speech", min_length=1, max_length=10000)
    voice: Optional[str] = Field(None, description="Voice model to use (defaults to service default)")
    speed: Optional[float] = Field(None, description="Speech speed multiplier (overrides the mode)", ge=0.5, le=2.0)
    noise_scale: Optional[float] = Field(None, description="Pitch/energy variation; lower is flatter (overrides the mode)", ge=0.0, le=1.5)
    mode: Optional[str] = Field(None, description="Voice mode for this request only (defaults to the active mode)")
    format: Literal["wav", "opus"] = "wav"


class ModeRequest(BaseModel):
    """Switch the active voice mode."""
    mode: str = Field(..., description="Mode name, or 'off'")


class VoiceInfo(BaseModel):
    """Information about an available voice."""
    name: str
    language: str
    speaker: str
    quality: str
    sample_rate: int
    gender: str
    file_size_mb: Optional[float] = None
    available: bool = True


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    voice_models_loaded: int
    default_voice: str
    models_directory: str


class DownloadVoiceRequest(BaseModel):
    """Request to download a new voice model."""
    voice_name: str = Field(..., description="Voice name to download (e.g., en_US-lessac-medium)")
    language: str = Field("en", description="Language code")
    country: str = Field("US", description="Country code")  
    speaker: str = Field("lessac", description="Speaker name")
    quality: str = Field("medium", description="Quality (low/medium/high)")


# Global state
config = ServiceConfig()
voice_models: Dict[str, piper.PiperVoice] = {}

# Setup logging
logger = setup_logging(config)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Service lifespan: startup and shutdown logic."""
    # Startup
    logger.info("Starting Piper TTS Service...")
    logger.info(f"Models directory: {config.models_dir}")
    logger.info(f"Default voice: {config.default_voice}")

    # Pre-load default voice model
    try:
        await load_voice_model(config.default_voice)
        logger.info("Default voice model loaded successfully")
    except Exception as e:
        logger.warning(f"Failed to pre-load default voice: {e}")

    logger.info("Piper TTS Service started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Piper TTS Service...")

    # Clear loaded models to free memory
    voice_models.clear()

    logger.info("Piper TTS Service shut down")


app = FastAPI(
    title="Piper TTS Service",
    description="HTTP API for Piper text-to-speech synthesis",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=".*",
    allow_methods=["*"],
    allow_headers=["*"],
)


class _HealthFilter(logging.Filter):
    def filter(self, record):
        return "/health" not in record.getMessage()


logging.getLogger("uvicorn.access").addFilter(_HealthFilter())


# Use extended voice catalog from config
VOICE_CATALOG = EXTENDED_VOICE_CATALOG


async def download_voice_model(voice_name: str) -> tuple[str, str]:
    """Download a voice model if it doesn't exist."""
    if voice_name not in VOICE_CATALOG:
        raise HTTPException(status_code=404, detail=f"Voice '{voice_name}' not found in catalog")
    
    model_path = config.models_dir / f"{voice_name}.onnx"
    config_path = config.models_dir / f"{voice_name}.onnx.json"
    
    if model_path.exists() and config_path.exists():
        logger.info(f"Voice model already exists: {voice_name}")
        return str(model_path), str(config_path)
    
    logger.info(f"Downloading voice model: {voice_name}")
    voice_info = VOICE_CATALOG[voice_name]
    base_url = voice_info["base_url"]
    
    try:
        # Download model file
        if not model_path.exists():
            model_url = f"{base_url}/{voice_name}.onnx"
            logger.info(f"Downloading model from {model_url}...")
            urllib.request.urlretrieve(model_url, str(model_path))
            logger.info(f"Model downloaded: {model_path}")
        
        # Download config file  
        if not config_path.exists():
            config_url = f"{base_url}/{voice_name}.onnx.json"
            logger.info(f"Downloading config from {config_url}...")
            urllib.request.urlretrieve(config_url, str(config_path))
            logger.info(f"Config downloaded: {config_path}")
            
        return str(model_path), str(config_path)
            
    except Exception as e:
        logger.error(f"Failed to download voice model {voice_name}: {e}")
        # Clean up partial downloads
        for path in [model_path, config_path]:
            if path.exists():
                path.unlink()
        raise HTTPException(status_code=500, detail=f"Failed to download voice model: {str(e)}")


async def load_voice_model(voice_name: str) -> piper.PiperVoice:
    """Load a voice model into memory."""
    if voice_name in voice_models:
        return voice_models[voice_name]
    
    try:
        # Download if needed
        model_path, config_path = await download_voice_model(voice_name)
        
        # Load model in executor to avoid blocking
        loop = asyncio.get_running_loop()
        voice_model = await loop.run_in_executor(
            None,
            piper.PiperVoice.load,
            model_path,
            config_path
        )
        
        voice_models[voice_name] = voice_model
        logger.info(f"Voice model loaded: {voice_name}")
        return voice_model
        
    except Exception as e:
        logger.error(f"Failed to load voice model {voice_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load voice model: {str(e)}")


def wav_to_opus(wav_bytes: bytes) -> bytes:
    in_buf = io.BytesIO(wav_bytes)
    out_buf = io.BytesIO()
    with av.open(in_buf, "r") as inp:
        with av.open(out_buf, "w", format="ogg") as out:
            in_stream = inp.streams.audio[0]
            out_stream = out.add_stream("libopus", rate=48000, layout="stereo", options={"application": "voip"})
            out_stream.bit_rate = 64000
            resampler = av.AudioResampler(format="s16", layout="stereo", rate=48000)
            for frame in inp.decode(in_stream):
                for resampled in resampler.resample(frame):
                    resampled.pts = None
                    for packet in out_stream.encode(resampled):
                        out.mux(packet)
            for resampled in resampler.resample(None):
                resampled.pts = None
                for packet in out_stream.encode(resampled):
                    out.mux(packet)
            for packet in out_stream.encode(None):
                out.mux(packet)
    return out_buf.getvalue()


MODE_OFF = "off"


def active_mode_path() -> Path:
    return config.state_dir / "active_mode"


def read_active_mode() -> str:
    try:
        return active_mode_path().read_text().strip() or MODE_OFF
    except FileNotFoundError:
        return MODE_OFF


def available_modes() -> List[str]:
    return sorted(p.stem for p in config.voice_modes_dir.glob("*.json"))


def load_mode(name: str) -> Dict[str, Any]:
    """Read a mode file fresh on every call so edits land without a restart."""
    if name == MODE_OFF:
        return {}
    path = config.voice_modes_dir / f"{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Voice mode '{name}' not found, choose from: {', '.join([MODE_OFF] + available_modes())}")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Voice mode '{name}' is not valid JSON: {e}")


def shodan_args(shodan: Dict[str, Any]) -> List[str]:
    args = [config.shodan_render, "-", "-"]
    if "preset" in shodan:
        args += ["--preset", str(shodan["preset"])]
    if "seed" in shodan:
        args += ["--seed", str(shodan["seed"])]
    if "rack" in shodan:
        rack = shodan["rack"]
        args += ["--rack", rack if isinstance(rack, str) else ",".join(rack)]
    for key, value in shodan.get("set", {}).items():
        args += ["--set", f"{key}={value}"]
    return args


def apply_shodan(wav_bytes: bytes, mode_name: str, shodan: Dict[str, Any]) -> bytes:
    """Pipe WAV through shodan-render. Fails open to the dry voice so a broken mode never goes silent."""
    args = shodan_args(shodan)
    try:
        result = subprocess.run(args, input=wav_bytes, capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        logger.error(f"Voice mode '{mode_name}' render failed, sending dry audio: {e}")
        return wav_bytes
    if result.returncode != 0 or not result.stdout:
        logger.error(f"Voice mode '{mode_name}' render exited {result.returncode}, sending dry audio: {result.stderr.decode(errors='replace').strip()}")
        return wav_bytes
    return result.stdout


def synthesize_audio_sync(text: str, voice_model: piper.PiperVoice, synth_args: Dict[str, float]) -> bytes:
    """Synchronous audio synthesis - runs in executor."""
    wav_buffer = io.BytesIO()
    
    try:
        with wave.open(wav_buffer, 'wb') as wav_file:
            # Configure WAV format parameters
            wav_file.setnchannels(1)  # Mono audio
            wav_file.setsampwidth(2)  # 16-bit samples
            wav_file.setframerate(voice_model.config.sample_rate)  # Use model's sample rate
            
            # Generate audio using the correct Piper API
            voice_model.synthesize(text, wav_file, **synth_args)
        
        return wav_buffer.getvalue()
        
    finally:
        wav_buffer.close()


# API Endpoints

@app.post("/tts", response_class=Response)
async def text_to_speech(request: TTSRequest) -> Response:
    """
    Convert text to speech and return WAV audio data.
    
    Returns audio/wav with the synthesized speech.
    """
    try:
        voice_name = request.voice or config.default_voice
        mode_name = request.mode or read_active_mode()
        mode = load_mode(mode_name)
        logger.info(f"TTS request: '{request.text[:50]}...' using voice '{voice_name}', mode '{mode_name}'")

        synth_args = {k: v for k, v in mode.get("piper", {}).items() if k in ("length_scale", "noise_scale", "noise_w")}
        if request.speed is not None:
            synth_args["length_scale"] = 1.0 / request.speed
        if request.noise_scale is not None:
            synth_args["noise_scale"] = request.noise_scale

        # Load voice model
        voice_model = await load_voice_model(voice_name)

        # Generate audio in executor
        loop = asyncio.get_running_loop()
        audio_data = await loop.run_in_executor(
            None,
            synthesize_audio_sync,
            request.text,
            voice_model,
            synth_args,
        )

        if "shodan" in mode:
            audio_data = await loop.run_in_executor(None, apply_shodan, audio_data, mode_name, mode["shodan"])

        logger.info(f"TTS completed: {len(audio_data)} bytes generated")

        if request.format == "opus":
            audio_data = await loop.run_in_executor(None, wav_to_opus, audio_data)
            return Response(
                content=audio_data,
                media_type="audio/ogg",
                headers={
                    "Content-Disposition": "inline; filename=\"speech.ogg\"",
                    "Content-Length": str(len(audio_data)),
                },
            )

        return Response(
            content=audio_data,
            media_type="audio/wav",
            headers={
                "Content-Disposition": "inline; filename=\"speech.wav\"",
                "Content-Length": str(len(audio_data))
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTS request failed: {e}")
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {str(e)}")


@app.get("/mode")
async def get_mode() -> Dict[str, Any]:
    """Active voice mode and the modes available to switch to."""
    return {"mode": read_active_mode(), "available": [MODE_OFF] + available_modes()}


@app.post("/mode")
async def set_mode(request: ModeRequest) -> Dict[str, Any]:
    """Switch the active voice mode for every /tts until switched again. Persists across restarts."""
    load_mode(request.mode)
    active_mode_path().write_text(request.mode + "\n")
    logger.info(f"Voice mode set to '{request.mode}'")
    return {"mode": request.mode}


@app.get("/voices", response_model=List[VoiceInfo])
async def list_voices() -> List[VoiceInfo]:
    """
    List all available voice models.
    
    Returns information about voices in the catalog and their availability.
    """
    voices = []
    
    for voice_name, info in VOICE_CATALOG.items():
        model_path = config.models_dir / f"{voice_name}.onnx"
        config_path = config.models_dir / f"{voice_name}.onnx.json"
        
        available = model_path.exists() and config_path.exists()
        file_size_mb = None
        
        if available and model_path.exists():
            file_size_mb = round(model_path.stat().st_size / (1024 * 1024), 1)
        
        voices.append(VoiceInfo(
            name=voice_name,
            language=info["language"],
            speaker=info["speaker"],
            quality=info["quality"],
            sample_rate=info["sample_rate"],
            gender=info["gender"],
            file_size_mb=file_size_mb,
            available=available
        ))
    
    return voices


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Service health check.
    
    Returns service status and loaded model information.
    """
    return HealthResponse(
        status="healthy",
        voice_models_loaded=len(voice_models),
        default_voice=config.default_voice,
        models_directory=str(config.models_dir)
    )


@app.post("/download-voice")
async def download_voice(request: DownloadVoiceRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """
    Download a new voice model.
    
    Downloads the specified voice model in the background.
    """
    voice_name = request.voice_name
    
    if voice_name not in VOICE_CATALOG:
        raise HTTPException(status_code=404, detail=f"Voice '{voice_name}' not found in catalog")
    
    model_path = config.models_dir / f"{voice_name}.onnx"
    config_path = config.models_dir / f"{voice_name}.onnx.json"
    
    if model_path.exists() and config_path.exists():
        return {
            "status": "already_exists",
            "message": f"Voice model '{voice_name}' already exists",
            "voice_name": voice_name
        }
    
    # Download in background
    background_tasks.add_task(download_voice_model, voice_name)
    
    return {
        "status": "downloading",
        "message": f"Voice model '{voice_name}' download started",
        "voice_name": voice_name
    }


if __name__ == "__main__":
    uvicorn.run(
        "service:app",
        host=config.host,
        port=config.port,
        log_level=config.log_level.lower(),
        reload=False
    )