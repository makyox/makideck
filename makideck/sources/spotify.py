"""Now playing in the Spotify desktop app, asked over AppleScript every second.

The script checks `application "Spotify" is running` first, so polling never
launches Spotify. macOS asks once whether makideck may control Spotify.
"""
from __future__ import annotations

import subprocess
import time

from ..state import Music
from ..store import Source

SCRIPT = '''
if application "Spotify" is running then
  tell application "Spotify"
    if player state is stopped then return "stopped"
    set t to current track
    return (player state as string) & tab & (name of t) & tab & (artist of t) ¬
      & tab & (player position as string) & tab & ((duration of t) as string) ¬
      & tab & (id of t)
  end tell
end if
return "off"
'''


def _number(text: str) -> float:
    return float(text.strip().replace(",", "."))     # locale decimal comma


def parse_player(out: str, polled_at: float) -> Music:
    fields = out.rstrip("\n").split("\t")
    if len(fields) < 6:
        state = fields[0].strip()
        return Music(state=state if state == "stopped" else "off", polled_at=polled_at)
    state, title, artist, pos, dur_ms, track = fields[:6]
    return Music(state=state, title=title, artist=artist, position_s=_number(pos),
                 duration_s=_number(dur_ms) / 1000, track_id=track, polled_at=polled_at)


class Spotify(Source):
    every = 1.0

    def poll(self) -> None:
        try:
            out = subprocess.run(["osascript", "-e", SCRIPT], capture_output=True,
                                 text=True, timeout=5).stdout
        except subprocess.TimeoutExpired:
            out = "off"
        self.store.set(music=parse_player(out, time.time()))
