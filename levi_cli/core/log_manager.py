"""Log file management."""

import re
import time
from pathlib import Path
from typing import Iterator, Optional


class LogManager:
    """Manages reading and parsing log files."""

    # ANSI color codes for log levels
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[34m",  # Blue
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def __init__(self, logs_dir: Path):
        self.logs_dir = logs_dir

    def get_log_path(self, service: str) -> Path:
        """Get log file path for a service."""
        log_files = {
            "mac-backend": "mac-backend.log",
            "telegram-bot": "telegram-bot.log",
        }
        return self.logs_dir / log_files.get(service, f"{service}.log")

    def tail(self, service: str, lines: int = 50) -> list[str]:
        """
        Get the last N lines from a log file.

        Args:
            service: Service name ('mac-backend' or 'telegram-bot')
            lines: Number of lines to retrieve

        Returns:
            List of log lines
        """
        log_path = self.get_log_path(service)

        if not log_path.exists():
            return []

        try:
            with open(log_path, "r") as f:
                # Read all lines and get the last N
                all_lines = f.readlines()
                return all_lines[-lines:]
        except Exception:
            return []

    def follow(self, service: str, colorize: bool = True) -> Iterator[str]:
        """
        Follow a log file (like tail -f).

        Args:
            service: Service name
            colorize: Whether to add color codes

        Yields:
            Log lines as they're written
        """
        log_path = self.get_log_path(service)

        # Wait for log file to exist if it doesn't
        while not log_path.exists():
            time.sleep(0.5)

        with open(log_path, "r") as f:
            # Move to end of file
            f.seek(0, 2)

            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.1)
                    continue

                if colorize:
                    line = self.colorize_line(line)

                yield line

    def colorize_line(self, line: str) -> str:
        """
        Add ANSI color codes to a log line based on level.

        Args:
            line: Log line

        Returns:
            Colored log line
        """
        # Try to detect log level in the line
        for level, color in self.COLORS.items():
            if level == "RESET":
                continue

            # Look for log level in various formats
            patterns = [
                rf"\b{level}\b",  # Standalone word
                rf"\[{level}\]",  # [INFO]
                rf"{level}:",  # INFO:
            ]

            for pattern in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    return f"{color}{line}{self.COLORS['RESET']}"

        # Default: no color
        return line

    def get_all_services(self) -> list[str]:
        """Get list of all services with log files."""
        if not self.logs_dir.exists():
            return []

        services = []
        for log_file in self.logs_dir.glob("*.log"):
            service_name = log_file.stem
            # Convert filename to service name format
            if service_name == "mac-backend":
                services.append("mac-backend")
            elif service_name == "telegram-bot":
                services.append("telegram-bot")

        return services
