"""Project discovery and path management."""

import os
from pathlib import Path
from typing import Optional


class ProjectPaths:
    """Container for all project-related paths."""

    def __init__(self, root: Path):
        self.root = root
        self.mac_dir = root / "mac"
        self.cloud_dir = root / "cloud"
        self.scripts_dir = root / "scripts"
        self.mac_env = self.mac_dir / ".env"
        self.cloud_env = self.cloud_dir / ".env"
        self.logs_dir = Path.home() / "levi" / "logs"
        self.launchagents_dir = Path.home() / "Library" / "LaunchAgents"
        self.mac_plist = self.launchagents_dir / "com.levi.mac-backend.plist"
        self.telegram_plist = self.launchagents_dir / "com.levi.telegram-bot.plist"


def find_project_root(start_path: Optional[Path] = None) -> Optional[Path]:
    """
    Find the Levi project root by looking for pyproject.toml with name="levi".

    Searches from the start_path (defaults to CWD) upwards until it finds
    a pyproject.toml file containing 'name = "levi"'.

    Args:
        start_path: Directory to start searching from (defaults to CWD)

    Returns:
        Path to project root, or None if not found
    """
    if start_path is None:
        start_path = Path.cwd()

    current = start_path.resolve()
    home = Path.home()

    # Search upwards until we hit home directory
    while current >= home:
        pyproject = current / "pyproject.toml"
        if pyproject.exists():
            # Check if this is the levi project
            try:
                content = pyproject.read_text()
                if 'name = "levi"' in content:
                    return current
            except Exception:
                pass

        # Also check for .git as a fallback indicator
        git_dir = current / ".git"
        claude_md = current / "CLAUDE.md"
        if git_dir.exists() and claude_md.exists():
            # Verify this looks like the levi project
            if (current / "mac").exists() and (current / "cloud").exists():
                return current

        if current == current.parent:
            break
        current = current.parent

    return None


def get_project_paths(start_path: Optional[Path] = None) -> ProjectPaths:
    """
    Get all project paths starting from a directory.

    Args:
        start_path: Directory to start searching from (defaults to CWD)

    Returns:
        ProjectPaths object

    Raises:
        RuntimeError: If project root cannot be found
    """
    root = find_project_root(start_path)
    if root is None:
        raise RuntimeError(
            "Could not find Levi project root. "
            "Make sure you're running this command from within the Levi project directory."
        )
    return ProjectPaths(root)
