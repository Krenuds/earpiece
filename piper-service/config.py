"""
Configuration management for Piper TTS Service.

Centralizes all configuration options and provides validation.
"""

import os
from pathlib import Path
from typing import Dict, Any
import logging
from logging.handlers import RotatingFileHandler


class ServiceConfig:
    """Service configuration with environment variable support and validation."""
    
    def __init__(self):
        # Server configuration
        self.host = os.getenv("PIPER_HOST", "0.0.0.0")
        self.port = int(os.getenv("PIPER_PORT", "9001"))
        
        # Model configuration  
        self.models_dir = Path(os.getenv("PIPER_MODELS_DIR", "models/piper"))
        self.default_voice = os.getenv("PIPER_DEFAULT_VOICE", "en_US-lessac-low")
        self.max_text_length = int(os.getenv("PIPER_MAX_TEXT_LENGTH", "10000"))

        # Voice modes: one <name>.json per mode, active mode persisted in the state dir
        self.voice_modes_dir = Path(os.getenv("PIPER_VOICE_MODES_DIR", "voicemodes"))
        self.state_dir = Path(os.getenv("PIPER_STATE_DIR", "state"))
        self.shodan_render = os.getenv("PIPER_SHODAN_RENDER", "shodan-render")

        # Logging
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        self.log_file = os.getenv("PIPER_LOG_FILE", "logs/piper-service.log")
        
        # Validation
        self._validate()
        
        # Ensure required directories exist
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        Path(self.log_file).parent.mkdir(parents=True, exist_ok=True)
    
    def _validate(self):
        """Validate configuration values."""
        if self.port < 1 or self.port > 65535:
            raise ValueError(f"Invalid port number: {self.port}")
        
        if self.max_text_length < 1:
            raise ValueError(f"Invalid max text length: {self.max_text_length}")

        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self.log_level not in valid_log_levels:
            raise ValueError(f"Invalid log level: {self.log_level}. Must be one of {valid_log_levels}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for logging/debugging."""
        return {
            'host': self.host,
            'port': self.port,
            'models_dir': str(self.models_dir),
            'default_voice': self.default_voice,
            'max_text_length': self.max_text_length,
            'voice_modes_dir': str(self.voice_modes_dir),
            'state_dir': str(self.state_dir),
            'log_level': self.log_level,
            'log_file': self.log_file
        }


# Extended voice catalog with more models
EXTENDED_VOICE_CATALOG = {
    # English (US) voices
    "en_US-lessac-medium": {
        "language": "English (US)",
        "speaker": "Lessac",
        "quality": "medium",
        "sample_rate": 22050,
        "gender": "female",
        "base_url": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium"
    },
    "en_US-lessac-low": {
        "language": "English (US)", 
        "speaker": "Lessac",
        "quality": "low",
        "sample_rate": 16000,
        "gender": "female",
        "base_url": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/low"
    },
    "en_US-amy-medium": {
        "language": "English (US)",
        "speaker": "Amy",
        "quality": "medium", 
        "sample_rate": 22050,
        "gender": "female",
        "base_url": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium"
    },
    "en_US-amy-low": {
        "language": "English (US)",
        "speaker": "Amy", 
        "quality": "low",
        "sample_rate": 16000,
        "gender": "female",
        "base_url": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/low"
    },
    "en_US-danny-low": {
        "language": "English (US)",
        "speaker": "Danny",
        "quality": "low",
        "sample_rate": 16000,
        "gender": "male", 
        "base_url": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/danny/low"
    },
    
    # English (GB) voices
    "en_GB-alan-medium": {
        "language": "English (GB)",
        "speaker": "Alan",
        "quality": "medium",
        "sample_rate": 22050,
        "gender": "male",
        "base_url": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/alan/medium"
    },
    "en_GB-alan-low": {
        "language": "English (GB)",
        "speaker": "Alan",
        "quality": "low", 
        "sample_rate": 16000,
        "gender": "male",
        "base_url": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/alan/low"
    },
    
    # Other languages (examples - expand as needed)
    "es_ES-marta-medium": {
        "language": "Spanish (Spain)",
        "speaker": "Marta",
        "quality": "medium",
        "sample_rate": 22050,
        "gender": "female",
        "base_url": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es/es_ES/marta/medium"
    },
    "fr_FR-upmc-medium": {
        "language": "French (France)",
        "speaker": "UPMC",
        "quality": "medium",
        "sample_rate": 22050,
        "gender": "female",
        "base_url": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/fr/fr_FR/upmc/medium"
    },
    "de_DE-thorsten-medium": {
        "language": "German (Germany)",
        "speaker": "Thorsten",
        "quality": "medium",
        "sample_rate": 22050,
        "gender": "male",
        "base_url": "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/de/de_DE/thorsten/medium"
    }
}


def setup_logging(config: ServiceConfig) -> logging.Logger:
    """Setup logging configuration for the service."""
    logger = logging.getLogger("piper-service")
    
    # Skip if already configured
    if logger.handlers:
        return logger
    
    logger.setLevel(getattr(logging, config.log_level))
    
    # Formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Rotating file handler (10 MB x 5 = ~50 MB cap)
    file_handler = RotatingFileHandler(
        config.log_file, maxBytes=10_000_000, backupCount=5
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    logger.propagate = False
    return logger