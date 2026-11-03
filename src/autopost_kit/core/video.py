"""Build vertical videos (Reels) with ffmpeg: one scene per item, then music.

A scene is either a still image (e.g. a cover) or a video clip shown in the
middle of the screen over a blurred, darker copy of itself. A transparent
overlay image with the texts goes on top. Topics only describe the scenes;
everything about ffmpeg lives here.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

WIDTH, HEIGHT, FPS = 1080, 1920, 30
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
ENCODE = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS)]

Runner = Callable[..., subprocess.CompletedProcess]


@dataclass
class Scene:
    label: str
    seconds: float
    overlay: Path | None = None  # transparent 1080x1920 PNG drawn on top
    still: Path | None = None  # full-frame image (cover)
    clip: Path | None = None  # local video file for the middle of the screen
    video_y: int = 560  # top of the video band when ``clip`` is used


def require_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError("ffmpeg not found. Install it with: winget install --id Gyan.FFmpeg -e")


def probe_duration(source: str, run: Runner = subprocess.run) -> float | None:
    result = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", source],
                 capture_output=True, text=True)
    try:
        return float((result.stdout or "").strip())
    except ValueError:
        return None


def clip_start(duration: float | None, seconds: float) -> float:
    """Skip the logos and ratings at the start of a trailer: take a stretch from about a third in."""
    if not duration:
        return 5.0
    return max(0.0, min(max(3.0, duration * 0.3), duration - seconds - 1.0))


def fetch_clip(source: str, out: Path, seconds: float, run: Runner = subprocess.run) -> Path:
    """Save ``seconds`` of ``source`` (a URL, HLS stream or file) to ``out``, without sound."""
    start = clip_start(probe_duration(source, run), seconds)
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-i", source, "-t", f"{seconds:.3f}",
         "-an", "-vf", f"scale={WIDTH}:-2,fps={FPS}", *ENCODE, str(out)], check=True)
    return out


def scene_command(scene: Scene, out: Path) -> list[str]:
    t = f"{scene.seconds:.3f}"
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    if scene.clip is not None:
        is_image = scene.clip.suffix.lower() in IMAGE_SUFFIXES  # no trailer: a screenshot stands in
        cmd += (["-loop", "1"] if is_image else ["-stream_loop", "-1"]) + ["-i", str(scene.clip)]
        layers = (
            f"[0:v]split=2[a][b];"
            f"[a]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT},"
            f"boxblur=30:2,eq=brightness=-0.22:saturation=0.8[bg];"
            f"[b]scale={WIDTH}:-2[fg];[bg][fg]overlay=0:{scene.video_y}[base]"
        )
    elif scene.still is not None:
        cmd += ["-loop", "1", "-i", str(scene.still)]
        layers = f"[0:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,pad={WIDTH}:{HEIGHT}:-1:-1[base]"
    else:
        raise ValueError(f"Scene {scene.label!r} needs a clip or a still image.")
    if scene.overlay is not None:
        cmd += ["-loop", "1", "-i", str(scene.overlay)]
        layers += ";[base][1:v]overlay=0:0[out]"
    else:
        layers += ";[base]null[out]"
    return cmd + ["-filter_complex", layers, "-map", "[out]", "-t", t, "-an", *ENCODE, str(out)]


def join_command(parts: list[Path], list_file: Path, track: Path | None, music_start: float, total: float,
                 out: Path) -> list[str]:
    list_file.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in parts), encoding="utf-8")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(list_file)]
    if track is None:
        return cmd + ["-c:v", "copy", "-an", "-movflags", "+faststart", str(out)]
    fade = max(0.0, total - 1.5)
    return cmd + [
        "-ss", f"{music_start:.3f}", "-t", f"{total:.3f}", "-i", str(track),
        "-map", "0:v", "-map", "1:a", "-c:v", "copy",
        "-af", f"afade=t=in:d=0.05,afade=t=out:st={fade:.3f}:d=1.5",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{total:.3f}",
        "-movflags", "+faststart", str(out),
    ]


def render(scenes: list[Scene], out: Path, work: Path, track: Path | None = None, music_start: float = 0.0,
           run: Runner = subprocess.run) -> float:
    """Render every scene and join them with the music. Returns the total length in seconds."""
    work.mkdir(parents=True, exist_ok=True)
    parts = []
    for n, scene in enumerate(scenes, start=1):
        part = work / f"scene_{n:02d}.mp4"
        log.info("Scene %d/%d: %s (%.1fs)", n, len(scenes), scene.label, scene.seconds)
        run(scene_command(scene, part), check=True)
        parts.append(part)
    total = sum(s.seconds for s in scenes)
    run(join_command(parts, work / "scenes.txt", track, music_start, total, out), check=True)
    return total
