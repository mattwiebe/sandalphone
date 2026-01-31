"""LaunchAgent service management."""

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class ServiceName(Enum):
    """Available services."""

    MAC_BACKEND = "com.levi.mac-backend"
    TELEGRAM_BOT = "com.levi.telegram-bot"

    @property
    def display_name(self) -> str:
        """Human-readable service name."""
        names = {
            self.MAC_BACKEND: "Mac Backend",
            self.TELEGRAM_BOT: "Telegram Bot",
        }
        return names[self]


@dataclass
class ServiceStatus:
    """Service status information."""

    name: ServiceName
    loaded: bool
    pid: Optional[int]
    last_exit: Optional[int]

    @property
    def is_running(self) -> bool:
        """Check if service is currently running."""
        return self.loaded and self.pid is not None and self.pid > 0

    @property
    def status_str(self) -> str:
        """Human-readable status string."""
        if not self.loaded:
            return "not loaded"
        elif not self.pid:
            return "loaded but not running"
        elif self.last_exit and self.last_exit != 0:
            return f"crashed (exit {self.last_exit})"
        else:
            return "running"

    @property
    def status_color(self) -> str:
        """Color for rich output."""
        if self.is_running:
            return "green"
        elif self.last_exit and self.last_exit != 0:
            return "yellow"
        else:
            return "red"


class LaunchAgentManager:
    """Manages macOS LaunchAgent services."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.plist_dir = Path.home() / "Library" / "LaunchAgents"
        self.domain = f"gui/{os.getuid()}"

    def get_status(self, service: ServiceName) -> ServiceStatus:
        """
        Get service status via launchctl list.

        Args:
            service: Service to check

        Returns:
            ServiceStatus object
        """
        try:
            result = subprocess.run(
                ["launchctl", "list"],
                capture_output=True,
                text=True,
                check=False,
            )

            # Parse output to find our service
            # Format: PID    Status    Label
            for line in result.stdout.splitlines():
                if service.value in line:
                    parts = line.split()
                    if len(parts) >= 3:
                        pid_str = parts[0]
                        status_str = parts[1]

                        # Parse PID (might be "-" if not running)
                        pid = None
                        if pid_str.isdigit():
                            pid = int(pid_str)

                        # Parse last exit code
                        last_exit = None
                        if status_str.isdigit():
                            last_exit = int(status_str)

                        return ServiceStatus(
                            name=service, loaded=True, pid=pid, last_exit=last_exit
                        )

            # Service not found in list - not loaded
            return ServiceStatus(name=service, loaded=False, pid=None, last_exit=None)

        except Exception as e:
            # If we can't run launchctl, assume not loaded
            return ServiceStatus(name=service, loaded=False, pid=None, last_exit=None)

    def start(self, service: ServiceName) -> tuple[bool, str]:
        """
        Bootstrap (load and start) service.

        Args:
            service: Service to start

        Returns:
            Tuple of (success, message)
        """
        plist_path = self.plist_dir / f"{service.value}.plist"

        if not plist_path.exists():
            return False, f"Plist not found: {plist_path}. Run 'levi deploy setup' first."

        # Check if already loaded
        status = self.get_status(service)
        if status.loaded:
            # If loaded but not running, use kickstart
            if not status.is_running:
                return self.restart(service)
            return True, f"{service.display_name} is already running"

        try:
            result = subprocess.run(
                ["launchctl", "bootstrap", self.domain, str(plist_path)],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                return True, f"{service.display_name} started successfully"
            else:
                return False, f"Failed to start {service.display_name}: {result.stderr}"

        except Exception as e:
            return False, f"Error starting {service.display_name}: {str(e)}"

    def stop(self, service: ServiceName) -> tuple[bool, str]:
        """
        Bootout (unload) service.

        Args:
            service: Service to stop

        Returns:
            Tuple of (success, message)
        """
        status = self.get_status(service)
        if not status.loaded:
            return True, f"{service.display_name} is not running"

        try:
            result = subprocess.run(
                ["launchctl", "bootout", f"{self.domain}/{service.value}"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                return True, f"{service.display_name} stopped successfully"
            else:
                return False, f"Failed to stop {service.display_name}: {result.stderr}"

        except Exception as e:
            return False, f"Error stopping {service.display_name}: {str(e)}"

    def restart(self, service: ServiceName) -> tuple[bool, str]:
        """
        Restart service (kill and let LaunchAgent restart it).

        Args:
            service: Service to restart

        Returns:
            Tuple of (success, message)
        """
        status = self.get_status(service)
        if not status.loaded:
            # Not loaded, try to start it
            return self.start(service)

        try:
            result = subprocess.run(
                ["launchctl", "kickstart", "-k", f"{self.domain}/{service.value}"],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                return True, f"{service.display_name} restarted successfully"
            else:
                return False, f"Failed to restart {service.display_name}: {result.stderr}"

        except Exception as e:
            return False, f"Error restarting {service.display_name}: {str(e)}"

    def install_plist(self, service: ServiceName) -> tuple[bool, str]:
        """
        Install (copy) plist from scripts/ to ~/Library/LaunchAgents/.

        Args:
            service: Service to install

        Returns:
            Tuple of (success, message)
        """
        source = self.project_root / "scripts" / f"{service.value}.plist"
        dest = self.plist_dir / f"{service.value}.plist"

        if not source.exists():
            return False, f"Source plist not found: {source}"

        try:
            # Ensure LaunchAgents directory exists
            self.plist_dir.mkdir(parents=True, exist_ok=True)

            # Copy plist
            shutil.copy(source, dest)

            return True, f"Installed {service.display_name} plist to {dest}"

        except Exception as e:
            return False, f"Error installing plist: {str(e)}"

    def uninstall_plist(self, service: ServiceName) -> tuple[bool, str]:
        """
        Remove plist from ~/Library/LaunchAgents/.

        Args:
            service: Service to uninstall

        Returns:
            Tuple of (success, message)
        """
        plist_path = self.plist_dir / f"{service.value}.plist"

        if not plist_path.exists():
            return True, f"{service.display_name} plist not installed"

        try:
            # Make sure service is stopped first
            status = self.get_status(service)
            if status.loaded:
                self.stop(service)

            # Remove plist
            plist_path.unlink()

            return True, f"Uninstalled {service.display_name} plist"

        except Exception as e:
            return False, f"Error uninstalling plist: {str(e)}"
