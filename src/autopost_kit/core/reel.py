"""Turn a built post (slide_01.png, ...) into a Reel MP4 with music, via ffmpeg."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

from autopost_kit.core.music import MusicLibrary, credit

log = logging.getLogger(__name__)

REEL_WIDTH, REEL_HEIGHT = 1080, 1920
MANIFEST = "reel.json"


def ffmpeg_command(slides_pattern: str, audio: Path, out: Path, slide_count: int,
                   seconds_per_slide: float, slide_size: tuple[int, int]) -> list[str]:
    w, h = slide_size
    total = slide_count * seconds_per_slide
    pad_y = max(0, (REEL_HEIGHT - h) // 2)
    video_filter = f"scale={w}:{h},pad={REEL_WIDTH}:{REEL_HEIGHT}:0:{pad_y}:black,fps=30,format=yuv420p"
    fade = max(0.0, total - 1.5)
    return [
        "ffmpeg", "-y", "-loglevel", "error",
        "-framerate", f"1/{seconds_per_slide:g}", "-start_number", "1", "-i", slides_pattern,
        "-i", str(audio),
        "-vf", video_filter,
        "-af", f"afade=t=out:st={fade:g}:d=1.5",
        "-t", f"{total:g}",
        "-c:v", "libx264", "-profile:v", "high", "-r", "30",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart",
        str(out),
    ]


def render_reel(post_dir: Path | str, music: MusicLibrary, track: Path | str | None = None,
                seconds_per_slide: float = 3.0, run=subprocess.run) -> dict:
    """Write ``reel.mp4``, ``reel_caption.txt`` and ``reel.json`` into ``post_dir``."""
    post_dir = Path(post_dir)
    slides = sorted(post_dir.glob("slide_*.png"))
    if not slides:
        raise FileNotFoundError(f"No slide_*.png in {post_dir}. Run 'autopost-kit build' first.")
    if run is subprocess.run and shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found. Install it with: winget install --id Gyan.FFmpeg -e")

    track = Path(track) if track else music.pick()
    from PIL import Image  # already a dependency (slides are rendered with Pillow)

    with Image.open(slides[0]) as img:
        size = img.size

    out = post_dir / "reel.mp4"
    cmd = ffmpeg_command(str(post_dir / "slide_%02d.png"), track, out, len(slides), seconds_per_slide, size)
    log.info("Rendering %s with %s", out, track.name)
    run(cmd, check=True)

    return _write_manifest(post_dir, out, track, music, len(slides) * seconds_per_slide)


def render_video_reel(post_dir: Path | str, topic, music: MusicLibrary, track: Path | str | None = None,
                      keep_work: bool = False) -> dict:
    """Reel built from video scenes (e.g. trailers), each cut on the beat of the song.

    ``topic`` provides ``reel_lengths(post)`` and ``reel_scenes(post, lengths, work)``.
    """
    from autopost_kit.core import beats, video
    from autopost_kit.core.output import load_post

    post_dir = Path(post_dir)
    video.require_ffmpeg()
    post = load_post(post_dir)
    track = Path(track) if track else music.pick()

    wanted = topic.reel_lengths(post)
    timing = beats.analyze(track, needed_seconds=sum(wanted))
    music_start, lengths = beats.plan(timing, wanted)
    if timing:
        log.info("%s: %.0f BPM, starting at %.1fs; scenes %s", track.name, timing.bpm, music_start,
                 ", ".join(f"{s:.1f}s" for s in lengths))

    work = post_dir / "_reel_work"
    scenes = topic.reel_scenes(post, lengths, work)
    out = post_dir / "reel.mp4"
    total = video.render(scenes, out, work, track=track, music_start=music_start)
    if not keep_work:
        shutil.rmtree(work, ignore_errors=True)
    return _write_manifest(post_dir, out, track, music, round(total, 2))


def _write_manifest(post_dir: Path, out: Path, track: Path, music: MusicLibrary, seconds: float) -> dict:
    caption_file = post_dir / "caption.txt"
    caption = caption_file.read_text(encoding="utf-8").rstrip() if caption_file.exists() else ""
    reel_caption = f"{caption}\n\n{credit(track)}\n" if caption else f"{credit(track)}\n"
    (post_dir / "reel_caption.txt").write_text(reel_caption, encoding="utf-8")

    manifest = {"video": out.name, "caption": "reel_caption.txt", "music": track.name,
                "music_folder": str(music.folder), "seconds": seconds}
    (post_dir / MANIFEST).write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def music_for_video(video: Path | str) -> tuple[str, str] | None:
    """(track name, music folder) recorded when ``video`` was rendered, if any."""
    manifest = Path(video).with_name(MANIFEST)
    if not manifest.exists():
        return None
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if data.get("video") != Path(video).name or not data.get("music"):
        return None
    return data["music"], data.get("music_folder", "music")
