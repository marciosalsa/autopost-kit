"""Save a built post to disk, ready for manual review and upload."""

from __future__ import annotations

import json
from pathlib import Path

from autopost_kit.core.models import Post


def save_post(post: Post, root: Path | str = "output") -> Path:
    """Write ``slide_01.png``…, ``caption.txt`` and ``post.json`` to ``root/<topic>/<date>/``."""
    folder = Path(root) / post.topic / post.target.isoformat()
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("slide_*.png"):
        old.unlink()

    files = []
    for n, slide in enumerate(post.slides, start=1):
        name = f"slide_{n:02d}.png"
        slide.image.convert("RGB").save(folder / name, optimize=True)
        files.append({"file": name, "label": slide.label})

    (folder / "caption.txt").write_text(post.caption, encoding="utf-8")
    manifest = {
        "topic": post.topic,
        "target": post.target.isoformat(),
        "total": post.total,
        "slides": files,
        "items": [item.to_dict() for item in post.items],
    }
    (folder / "post.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return folder


def load_post(folder: Path | str) -> dict:
    """Read ``post.json`` back; ``items`` become :class:`Item` objects again."""
    from autopost_kit.core.models import Item

    folder = Path(folder)
    path = folder / "post.json"
    if not path.exists():
        raise FileNotFoundError(f"No post.json in {folder}. Run 'autopost-kit build' first.")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["items"] = [Item.from_dict(item) for item in data.get("items", [])]
    return data
