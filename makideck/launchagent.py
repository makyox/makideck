"""Start makideck at login: a launchd agent that runs the menu bar app (which
then runs the deck). Quitting from the menu stays quit; a crash restarts.
"""
from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

from .config import LOG_DIR

LABEL = "io.github.makyox.makideck"
PLIST = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def plist() -> dict:
    # sys.executable, not resolved: in a venv it's a symlink, and following
    # it would start the bare interpreter without our packages.
    npx = shutil.which("npx")
    path = [str(Path(npx).parent)] if npx else []
    path += ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"]
    return {
        "Label": LABEL,
        "ProgramArguments": [sys.executable, "-m", "makideck", "menubar"],
        "EnvironmentVariables": {"PATH": ":".join(path)},   # launchd's is bare
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},
        "ThrottleInterval": 10,
        "StandardOutPath": str(LOG_DIR / "launchd.log"),
        "StandardErrorPath": str(LOG_DIR / "launchd.log"),
    }


def _launchctl(*args: str) -> bool:
    return subprocess.run(["launchctl", *args], capture_output=True).returncode == 0


def installed() -> bool:
    return PLIST.exists()


def install(start: bool = True) -> None:
    """start=False just writes the plist (it runs from the next login)."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if start:
        _launchctl("bootout", f"gui/{os.getuid()}/{LABEL}")
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    PLIST.write_bytes(plistlib.dumps(plist()))
    if start and not _launchctl("bootstrap", f"gui/{os.getuid()}", str(PLIST)):
        raise SystemExit(f"launchctl could not load {PLIST}")


def uninstall(stop: bool = True) -> None:
    if stop:
        _launchctl("bootout", f"gui/{os.getuid()}/{LABEL}")
    PLIST.unlink(missing_ok=True)
