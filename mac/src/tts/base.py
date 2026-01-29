"""
Abstract base class for TTS (Text-to-Speech) providers.

This module defines the interface that all TTS providers must implement,
enabling easy swapping between different TTS engines (Qwen, VibeVoice, etc.).
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class TTSProvider(ABC):
    """Abstract base class for TTS providers."""

    @abstractmethod
    def synthesize(
        self, text: str, output_file: Optional[Path] = None, language: str = "en"
    ) -> Path:
        """
        Synthesize speech from text.

        Args:
            text: Text to synthesize
            output_file: Optional output path (generates temp file if None)
            language: Language code ("en" for English, "es" for Spanish)

        Returns:
            Path to generated audio file (WAV format)
        """
        pass
