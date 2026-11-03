import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest
from PIL import Image

from autopost_kit.core import beats, video
from autopost_kit.core.models import Item
from autopost_kit.core.video import Scene
from autopost_kit.topics.steam_releases import collector, layout
from autopost_kit.topics.steam_releases.topic import SteamReleasesTopic

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


# --- beat planning -----------------------------------------------------------

def timing(bpm=120.0, start_index=8, n=400):
    step = 60.0 / bpm
    return beats.TrackTiming(bpm=bpm, beats=[i * step for i in range(n)], start_index=start_index, duration=n * step)


def test_plan_snaps_scenes_to_whole_bars():
    start, lengths = beats.plan(timing(bpm=120), [3.7, 11.0, 11.0])

    assert start == pytest.approx(4.0)  # beat 8 at 0.5s per beat
    # one bar = 2s at 120 BPM: 3.7s -> 2 bars, 11s -> 6 bars (5.5 rounds to 6)
    assert lengths == pytest.approx([4.0, 12.0, 12.0])


def test_plan_without_analysis_keeps_requested_lengths():
    assert beats.plan(None, [3.7, 11.0]) == (0.0, [3.7, 11.0])


def test_plan_continues_past_detected_beats():
    _, lengths = beats.plan(timing(bpm=120, start_index=0, n=10), [8.0, 8.0])

    assert lengths == pytest.approx([8.0, 8.0])


def test_strong_part_skips_quiet_intro_and_short_climax():
    energy = [0.08, 0.08, 0.10, 0.20, 0.30, 0.30, 0.29, 0.30, 0.30, 0.35, 0.30]

    assert beats.strong_part_start(energy, min_bars_after=2) == 4


def test_analysis_is_cached_next_to_the_track(tmp_path):
    track = tmp_path / "song.mp3"
    track.write_bytes(b"")
    beats.cache_path(track).write_text(json.dumps({"bpm": 128.0, "beats": [0.0, 0.5], "start_index": 0,
                                                   "duration": 1.0}))

    assert beats.analyze(track).bpm == 128.0


# --- trailers --------------------------------------------------------------

def test_pick_trailer_prefers_highlight_and_hls():
    movies = [
        {"id": 1, "highlight": False, "hls_h264": "https://video/1.m3u8"},
        {"id": 2, "highlight": True, "hls_h264": "https://video/2.m3u8"},
    ]

    assert collector.pick_trailer(movies) == "https://video/2.m3u8"
    assert collector.pick_trailer([{"mp4": {"max": "https://video/old.mp4"}}]) == "https://video/old.mp4"
    assert collector.pick_trailer([]) is None


def test_clip_start_skips_intro_but_fits_the_clip():
    assert video.clip_start(90.0, 11) == pytest.approx(27.0)
    assert video.clip_start(14.0, 11) == pytest.approx(2.0)
    assert video.clip_start(None, 11) == 5.0


def test_scene_command_layers_video_over_blurred_copy(tmp_path):
    scene = Scene(label="#1", seconds=10.2, overlay=tmp_path / "o.png", clip=tmp_path / "c.mp4", video_y=520)

    cmd = " ".join(video.scene_command(scene, tmp_path / "out.mp4"))

    assert "-stream_loop -1" in cmd and "boxblur" in cmd and "overlay=0:520" in cmd
    assert "-t 10.200" in cmd


def test_scene_command_uses_loop_for_screenshot_fallback(tmp_path):
    cmd = video.scene_command(Scene(label="#2", seconds=5, clip=tmp_path / "s.jpg"), tmp_path / "o.mp4")

    assert cmd[cmd.index("-i") - 2:cmd.index("-i")] == ["-loop", "1"]


# --- layout ----------------------------------------------------------------

def test_reel_overlay_is_transparent_full_frame():
    game = Item(id="1", title="Example Quest", url="u", date=date(2026, 11, 4),
                meta={"display_genres": ["Action", "RPG"], "developers": ["Example Studio"], "badge": "EARLY ACCESS"})
    topic = SteamReleasesTopic(store=object(), fetch_image=lambda url: None)
    from autopost_kit.core.i18n import load_strings

    layer = layout.render_reel_overlay(topic.theme, load_strings(topic.config_package), date(2026, 11, 4), game, 1,
                                       lambda url: None)

    assert layer.size == (1080, 1920) and layer.mode == "RGBA"
    assert layer.getpixel((540, layout.REEL_VIDEO_Y + 300))[3] == 0  # the trailer band stays see-through


# --- end to end with the real ffmpeg -----------------------------------------

@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not installed")
def test_render_joins_scenes_with_music(tmp_path):
    clip = tmp_path / "trailer.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=30",
                    "-t", "3", "-pix_fmt", "yuv420p", str(clip)], check=True)
    song = tmp_path / "song.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440",
                    "-t", "10", str(song)], check=True)
    cover = tmp_path / "cover.png"
    Image.new("RGB", (1080, 1350), (13, 17, 23)).save(cover)
    overlay = tmp_path / "overlay.png"
    Image.new("RGBA", (1080, 1920), (0, 0, 0, 0)).save(overlay)

    out = tmp_path / "reel.mp4"
    total = video.render(
        [Scene("cover", 1.0, still=cover), Scene("#1", 2.0, overlay=overlay, clip=clip)],
        out, tmp_path / "work", track=song, music_start=1.0,
    )

    assert total == pytest.approx(3.0)
    assert video.probe_duration(str(out)) == pytest.approx(3.0, abs=0.15)
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height", "-of", "csv=p=0", str(out)], capture_output=True, text=True)
    assert probe.stdout.strip() == "1080,1920"
