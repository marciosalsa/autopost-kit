import json
import random

import pytest

from autopost_kit.core.music import MusicLibrary, credit
from autopost_kit.core.reel import ffmpeg_command, music_for_video, render_reel


def make_library(tmp_path, names):
    folder = tmp_path / "music"
    folder.mkdir()
    for name in names:
        (folder / name).write_bytes(b"fake audio")
    return MusicLibrary(folder, rng=random.Random(0))


def test_pick_prefers_unused_tracks(tmp_path):
    lib = make_library(tmp_path, ["A - One.mp3", "B - Two.mp3", "notes.md"])
    lib.mark_used("A - One.mp3")
    assert lib.pick().name == "B - Two.mp3"


def test_pick_reuses_least_recently_used_when_all_used(tmp_path):
    lib = make_library(tmp_path, ["A.mp3", "B.mp3"])
    lib.log_path.write_text(json.dumps([
        {"track": "A.mp3", "used_at": "2026-11-01T10:00:00+00:00"},
        {"track": "B.mp3", "used_at": "2026-11-02T10:00:00+00:00"},
        {"track": "A.mp3", "used_at": "2026-11-03T10:00:00+00:00"},
    ]), encoding="utf-8")
    assert lib.pick().name == "B.mp3"


def test_mark_used_appends_to_the_log(tmp_path):
    lib = make_library(tmp_path, ["A.mp3"])
    lib.mark_used("A.mp3", media_id="123")
    lib.mark_used("A.mp3")
    history = json.loads(lib.log_path.read_text(encoding="utf-8"))
    assert [h["track"] for h in history] == ["A.mp3", "A.mp3"]
    assert history[0]["media_id"] == "123"


def test_pick_without_music_fails_clearly(tmp_path):
    with pytest.raises(FileNotFoundError):
        MusicLibrary(tmp_path / "nothing").pick()


def test_credit_from_file_name_and_from_txt(tmp_path):
    lib = make_library(tmp_path, ["Laeko - DON'T WANNA KNOW!!! [NCS Release].mp3", "X - Y.mp3"])
    assert credit(lib.folder / "Laeko - DON'T WANNA KNOW!!! [NCS Release].mp3") == (
        "🎵 Song: Laeko - DON'T WANNA KNOW!!!\nMusic provided by NoCopyrightSounds")
    (lib.folder / "X - Y.txt").write_text("custom credit\n", encoding="utf-8")
    assert credit(lib.folder / "X - Y.mp3") == "custom credit"


def test_ffmpeg_command_centers_slides_and_cuts_to_length():
    cmd = ffmpeg_command("slide_%02d.png", "song.mp3", "reel.mp4", 6, 3.0, (1080, 1350))
    assert "-t" in cmd and cmd[cmd.index("-t") + 1] == "18"
    assert "pad=1080:1920:0:285:black" in cmd[cmd.index("-vf") + 1]


def test_render_reel_writes_caption_and_manifest_without_logging_music(tmp_path):
    from PIL import Image

    post = tmp_path / "post"
    post.mkdir()
    for n in (1, 2):
        Image.new("RGB", (1080, 1350)).save(post / f"slide_{n:02d}.png")
    (post / "caption.txt").write_text("Caption\n", encoding="utf-8")
    lib = make_library(tmp_path, ["A - Song.mp3"])
    calls = []

    manifest = render_reel(post, lib, run=lambda cmd, check: calls.append(cmd))

    assert calls and manifest["music"] == "A - Song.mp3"
    assert (post / "reel_caption.txt").read_text(encoding="utf-8") == "Caption\n\n🎵 Song: A - Song\n"
    assert music_for_video(post / "reel.mp4") == ("A - Song.mp3", str(lib.folder))
    assert lib.history() == []  # only a real publish marks a song as used
