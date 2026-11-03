"""Cut video on the beat.

A track is analysed once (tempo, beat times and where the strong part starts)
and the result is cached next to it as ``<track>.beats.json``. Scene lengths
are then rounded to whole bars (4 beats) and every cut lands on a downbeat.

The analysis needs the optional ``librosa`` package
(``pip install -e ".[music]"``). Without it, scenes keep the requested
lengths and the music starts at its beginning.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

log = logging.getLogger(__name__)

BEATS_PER_BAR = 4


@dataclass
class TrackTiming:
    bpm: float
    beats: list[float]
    start_index: int
    duration: float

    @property
    def bar_seconds(self) -> float:
        return BEATS_PER_BAR * 60.0 / self.bpm

    @property
    def start(self) -> float:
        return self.beats[self.start_index]


def cache_path(track: Path) -> Path:
    return track.with_name(track.name + ".beats.json")


def strong_part_start(bar_energy: list[float], min_bars_after: int) -> int:
    """Index of the first bar where the track reaches its "full" level and stays there.

    "Full" is 85% of the average of the loudest quarter of bars, which ignores
    a short climax and finds the first chorus or drop.
    """
    if not bar_energy:
        return 0
    loud = sorted(bar_energy, reverse=True)[: max(1, len(bar_energy) // 4)]
    level = 0.85 * sum(loud) / len(loud)
    last_possible = max(0, len(bar_energy) - min_bars_after)
    for i in range(min(last_possible, len(bar_energy) - 1) + 1):
        if bar_energy[i] >= level and (i + 1 >= len(bar_energy) or bar_energy[i + 1] >= level):
            return i
    return 0


def analyze(track: Path | str, needed_seconds: float = 60.0) -> TrackTiming | None:
    track = Path(track)
    cached = cache_path(track)
    if cached.exists():
        try:
            return TrackTiming(**json.loads(cached.read_text(encoding="utf-8")))
        except (ValueError, TypeError):
            log.warning("Ignoring unreadable %s", cached)
    try:
        import librosa
        import numpy as np
    except ImportError:
        log.warning("librosa is not installed: cuts will not follow the beat (pip install -e \".[music]\").")
        return None

    log.info("Analysing %s (done once, then cached)...", track.name)
    y, sr = librosa.load(str(track), sr=22050, mono=True)
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units="time")
    beats = [float(b) for b in beats]
    if len(beats) < 2 * BEATS_PER_BAR:
        return None
    rms = librosa.feature.rms(y=y)[0]
    times = librosa.times_like(rms, sr=sr)
    energy = []
    for i in range(0, len(beats) - BEATS_PER_BAR, BEATS_PER_BAR):
        mask = (times >= beats[i]) & (times < beats[i + BEATS_PER_BAR])
        energy.append(float(rms[mask].mean()) if mask.any() else 0.0)
    bpm = float(np.atleast_1d(tempo)[0])
    bars_needed = int(needed_seconds / (BEATS_PER_BAR * 60.0 / bpm)) + 1
    timing = TrackTiming(bpm=bpm, beats=beats, start_index=BEATS_PER_BAR * strong_part_start(energy, bars_needed),
                         duration=len(y) / sr)
    cached.write_text(json.dumps(asdict(timing)), encoding="utf-8")
    log.info("%s: %.0f BPM, strong part at %.1fs", track.name, timing.bpm, timing.start)
    return timing


def plan(timing: TrackTiming | None, wanted: list[float]) -> tuple[float, list[float]]:
    """Music start and the real length of each scene, snapped to whole bars."""
    if timing is None:
        return 0.0, list(wanted)
    lengths: list[float] = []
    index = timing.start_index
    for seconds in wanted:
        bars = max(1, round(seconds / timing.bar_seconds))
        end = index + bars * BEATS_PER_BAR
        if end < len(timing.beats):
            lengths.append(timing.beats[end] - timing.beats[index])
        else:  # ran past the detected beats: keep the tempo
            lengths.append(bars * timing.bar_seconds)
        index = end
    return timing.start, lengths
