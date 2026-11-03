"""Music library for Reels: pick a track that hasn't been used yet.

Tracks live in a folder (``music/`` by default). Every published Reel is
recorded in ``used.json`` inside that folder, so the same song is not used
twice. When every track has been used, the one used longest ago comes back.

Credits: a text file next to a track with the same name (``Song.mp3`` ->
``Song.txt``) is used as the caption credit. Without it, a credit is built
from the file name ("Artist - Title [NCS Release].mp3").
"""

from __future__ import annotations

import json
import logging
import random
import re
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

AUDIO_EXTENSIONS = {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".flac"}
LOG_NAME = "used.json"


class MusicLibrary:
    def __init__(self, folder: Path | str = "music", rng: random.Random | None = None) -> None:
        self.folder = Path(folder)
        self.log_path = self.folder / LOG_NAME
        self.rng = rng or random.Random()

    # --- tracks -----------------------------------------------------------
    def tracks(self) -> list[Path]:
        if not self.folder.is_dir():
            return []
        return sorted(p for p in self.folder.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS)

    def history(self) -> list[dict]:
        if not self.log_path.exists():
            return []
        try:
            data = json.loads(self.log_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            log.warning("Could not read %s; treating every track as unused.", self.log_path)
            return []
        return data if isinstance(data, list) else []

    def last_used(self) -> dict[str, str]:
        """Track file name -> last time it was used (ISO timestamp)."""
        latest: dict[str, str] = {}
        for entry in self.history():
            name, when = entry.get("track"), entry.get("used_at", "")
            if name and when >= latest.get(name, ""):
                latest[name] = when
        return latest

    def pick(self) -> Path:
        """An unused track at random; if all were used, the least recently used one."""
        tracks = self.tracks()
        if not tracks:
            raise FileNotFoundError(f"No music found in {self.folder}/ ({', '.join(sorted(AUDIO_EXTENSIONS))})")
        used = self.last_used()
        unused = [t for t in tracks if t.name not in used]
        if unused:
            choice = self.rng.choice(unused)
            log.info("Music: %s (%d unused left after this one)", choice.name, len(unused) - 1)
            return choice
        choice = min(tracks, key=lambda t: used[t.name])
        log.warning("Every track was already used; reusing %s. Add more songs to %s/.", choice.name, self.folder)
        return choice

    def mark_used(self, track: Path | str, **details: str) -> None:
        entry = {"track": Path(track).name, "used_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        entry.update({k: v for k, v in details.items() if v})
        history = self.history()
        history.append(entry)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text(json.dumps(history, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        log.info("Logged %s as used in %s", entry["track"], self.log_path)


def credit(track: Path | str) -> str:
    """Caption credit for ``track``: its ``.txt`` file if present, else built from the name."""
    track = Path(track)
    custom = track.with_suffix(".txt")
    if custom.exists():
        return custom.read_text(encoding="utf-8").strip()
    stem = track.stem
    ncs = bool(re.search(r"\[\s*NCS Release\s*\]", stem, re.IGNORECASE))
    title = re.sub(r"\s*\[[^\]]*\]\s*", " ", stem).strip()
    lines = [f"🎵 Song: {title}"]
    if ncs:
        lines.append("Music provided by NoCopyrightSounds")
    return "\n".join(lines)
