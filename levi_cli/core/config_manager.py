"""Configuration management."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import dotenv_values


@dataclass
class MacConfig:
    """Mac backend configuration."""

    tts_provider: Optional[str] = None
    tts_model_path: Optional[str] = None
    log_level: str = "INFO"

    @classmethod
    def from_env(cls, env_path: Path) -> "MacConfig":
        """Load configuration from .env file."""
        if not env_path.exists():
            return cls()

        env = dotenv_values(env_path)
        return cls(
            tts_provider=env.get("TTS_PROVIDER"),
            tts_model_path=env.get("TTS_MODEL_PATH"),
            log_level=env.get("LOG_LEVEL", "INFO"),
        )

    def validate(self) -> List[str]:
        """
        Validate configuration.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if self.tts_provider and self.tts_provider not in ["vibevoice", "qwen"]:
            errors.append(f"Invalid TTS_PROVIDER: {self.tts_provider}")

        if self.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            errors.append(f"Invalid LOG_LEVEL: {self.log_level}")

        return errors

    def to_dict(self, redact: bool = True) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "TTS_PROVIDER": self.tts_provider or "-",
            "TTS_MODEL_PATH": self.tts_model_path or "-",
            "LOG_LEVEL": self.log_level,
        }


@dataclass
class CloudConfig:
    """Cloud bot configuration."""

    telegram_bot_token: Optional[str] = None
    telegram_api_id: Optional[str] = None
    telegram_api_hash: Optional[str] = None
    mac_websocket_url: Optional[str] = None
    allowed_user_ids: List[str] = field(default_factory=list)
    voice_call_enabled: bool = True
    auto_join_voice_chats: bool = True
    default_source_lang: str = "es"
    default_target_lang: str = "en"
    vad_aggressiveness: int = 2
    silence_duration_ms: int = 500
    log_level: str = "INFO"

    @classmethod
    def from_env(cls, env_path: Path) -> "CloudConfig":
        """Load configuration from .env file."""
        if not env_path.exists():
            return cls()

        env = dotenv_values(env_path)

        # Parse allowed user IDs
        user_ids = []
        if env.get("ALLOWED_USER_IDS"):
            user_ids = [uid.strip() for uid in env["ALLOWED_USER_IDS"].split(",") if uid.strip()]

        return cls(
            telegram_bot_token=env.get("TELEGRAM_BOT_TOKEN"),
            telegram_api_id=env.get("TELEGRAM_API_ID"),
            telegram_api_hash=env.get("TELEGRAM_API_HASH"),
            mac_websocket_url=env.get("MAC_WEBSOCKET_URL"),
            allowed_user_ids=user_ids,
            voice_call_enabled=env.get("VOICE_CALL_ENABLED", "true").lower() == "true",
            auto_join_voice_chats=env.get("AUTO_JOIN_VOICE_CHATS", "true").lower() == "true",
            default_source_lang=env.get("DEFAULT_SOURCE_LANG", "es"),
            default_target_lang=env.get("DEFAULT_TARGET_LANG", "en"),
            vad_aggressiveness=int(env.get("VAD_AGGRESSIVENESS", "2")),
            silence_duration_ms=int(env.get("SILENCE_DURATION_MS", "500")),
            log_level=env.get("LOG_LEVEL", "INFO"),
        )

    def validate(self) -> List[str]:
        """
        Validate configuration.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if not self.telegram_bot_token:
            errors.append("TELEGRAM_BOT_TOKEN is required")

        if not self.mac_websocket_url:
            errors.append("MAC_WEBSOCKET_URL is required")
        elif not self.mac_websocket_url.startswith("ws://") and not self.mac_websocket_url.startswith("wss://"):
            errors.append("MAC_WEBSOCKET_URL must start with ws:// or wss://")

        if self.vad_aggressiveness not in [0, 1, 2, 3]:
            errors.append("VAD_AGGRESSIVENESS must be 0, 1, 2, or 3")

        if self.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            errors.append(f"Invalid LOG_LEVEL: {self.log_level}")

        return errors

    def to_dict(self, redact: bool = True) -> Dict[str, Any]:
        """Convert to dictionary."""
        token = self.telegram_bot_token or ""
        api_hash = self.telegram_api_hash or ""

        return {
            "TELEGRAM_BOT_TOKEN": "********" + token[-4:] if (redact and token) else (token or "-"),
            "TELEGRAM_API_ID": self.telegram_api_id or "-",
            "TELEGRAM_API_HASH": "********" + api_hash[-4:] if (redact and api_hash) else (api_hash or "-"),
            "MAC_WEBSOCKET_URL": self.mac_websocket_url or "-",
            "ALLOWED_USER_IDS": ", ".join(self.allowed_user_ids) if self.allowed_user_ids else "-",
            "VOICE_CALL_ENABLED": str(self.voice_call_enabled),
            "AUTO_JOIN_VOICE_CHATS": str(self.auto_join_voice_chats),
            "DEFAULT_SOURCE_LANG": self.default_source_lang,
            "DEFAULT_TARGET_LANG": self.default_target_lang,
            "VAD_AGGRESSIVENESS": str(self.vad_aggressiveness),
            "SILENCE_DURATION_MS": str(self.silence_duration_ms),
            "LOG_LEVEL": self.log_level,
        }
