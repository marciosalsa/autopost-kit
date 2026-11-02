"""Drawing primitives shared by every topic's slide templates.

Topics decide *what* goes on a slide; this module knows *how* to draw it:
fonts, text that fits a box, cropped backgrounds, gradients, pills.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any

from PIL import Image, ImageDraw, ImageFont

FONTS_PACKAGE = "autopost_kit.assets.fonts"
FONT_FILES = {
    "display": "BebasNeue-Regular.ttf",  # condensed titles
    "text": "Inter-Variable.ttf",  # body text, variable weight
}

RGB = tuple[int, int, int]


def hex_to_rgb(value: str) -> RGB:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


@dataclass(frozen=True)
class Theme:
    """Visual identity of a channel. Loaded from a topic's ``theme`` config."""

    width: int = 1080
    height: int = 1350
    margin: int = 64
    background: str = "#0d1117"
    accent: str = "#7cf2c7"
    text: str = "#f2f5f9"
    muted: str = "#9aa7b6"
    divider: str = "#232a33"
    on_accent: str = "#06120d"

    @classmethod
    def from_config(cls, config: dict[str, Any] | None) -> "Theme":
        known = {k: v for k, v in (config or {}).items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def rgb(self, name: str) -> RGB:
        return hex_to_rgb(getattr(self, name))

    @property
    def size(self) -> tuple[int, int]:
        return self.width, self.height


@lru_cache(maxsize=64)
def font(family: str, size: int, weight: str | None = None) -> ImageFont.FreeTypeFont:
    """Load a bundled font. ``weight`` names a variation such as ``Bold``."""
    path = resources.files(FONTS_PACKAGE).joinpath(FONT_FILES[family])
    with resources.as_file(path) as real_path:
        loaded = ImageFont.truetype(str(real_path), size)
    if weight:
        loaded.set_variation_by_name(weight)
    return loaded


def text_width(text: str, typeface: ImageFont.FreeTypeFont) -> int:
    left, _, right, _ = typeface.getbbox(text)
    return right - left


def truncate(text: str, typeface: ImageFont.FreeTypeFont, max_width: int) -> str:
    """Cut ``text`` with an ellipsis so it fits in ``max_width`` pixels."""
    if text_width(text, typeface) <= max_width:
        return text
    while text and text_width(text + "…", typeface) > max_width:
        text = text[:-1]
    return text.rstrip() + "…"


def wrap(text: str, typeface: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if not current or text_width(candidate, typeface) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def fit_lines(
    text: str,
    family: str,
    max_width: int,
    sizes: tuple[int, ...],
    max_lines: int = 2,
    weight: str | None = None,
) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    """Largest size in ``sizes`` where ``text`` wraps into ``max_lines`` or fewer.

    If nothing fits, the smallest size is used and the last line is truncated.
    """
    for size in sizes:
        typeface = font(family, size, weight)
        lines = wrap(text, typeface, max_width)
        if len(lines) <= max_lines and all(text_width(l, typeface) <= max_width for l in lines):
            return typeface, lines
    typeface = font(family, sizes[-1], weight)
    lines = wrap(text, typeface, max_width)[:max_lines]
    lines[-1] = truncate(lines[-1], typeface, max_width)
    return typeface, lines


def cover_crop(image: Image.Image, width: int, height: int) -> Image.Image:
    """Scale and center-crop ``image`` so it fills width × height (like CSS ``cover``)."""
    image = image.convert("RGB")
    scale = max(width / image.width, height / image.height)
    resized = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def vertical_fade(width: int, height: int, color: RGB, stops: list[tuple[float, float]]) -> Image.Image:
    """An RGBA layer of ``color`` whose opacity follows ``stops`` [(position 0-1, alpha 0-1)]."""
    column = Image.new("L", (1, height))
    pixels = column.load()
    stops = sorted(stops)
    for y in range(height):
        pos = y / max(height - 1, 1)
        alpha = stops[-1][1]
        for (p0, a0), (p1, a1) in zip(stops, stops[1:]):
            if p0 <= pos <= p1:
                t = 0 if p1 == p0 else (pos - p0) / (p1 - p0)
                alpha = a0 + (a1 - a0) * t
                break
        else:
            if pos < stops[0][0]:
                alpha = stops[0][1]
        pixels[0, y] = round(alpha * 255)
    layer = Image.new("RGBA", (width, height), color + (0,))
    layer.putalpha(column.resize((width, height)))
    return layer


def rounded(image: Image.Image, radius: int) -> Image.Image:
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *image.size), radius=radius, fill=255)
    out = image.convert("RGBA")
    out.putalpha(mask)
    return out


def pill(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, typeface: ImageFont.FreeTypeFont,
         fill: RGB, color: RGB, pad: tuple[int, int] = (30, 14)) -> tuple[int, int]:
    """Draw a rounded label at ``xy`` (top-left). Returns its (width, height)."""
    left, top, right, bottom = typeface.getbbox(text)
    w = right - left + pad[0] * 2
    h = bottom - top + pad[1] * 2
    x, y = xy
    draw.rounded_rectangle((x, y, x + w, y + h), radius=h // 2, fill=fill)
    draw.text((x + pad[0] - left, y + pad[1] - top), text, font=typeface, fill=color)
    return w, h
