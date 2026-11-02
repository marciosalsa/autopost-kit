"""Slide templates for @tomorrowonsteam.

Carousel order: a cover listing the top games 1 → N, then one slide per game
counting down N → 1, so the most anticipated game is the last reveal.
"""

from __future__ import annotations

from datetime import date

from PIL import Image, ImageDraw

from autopost_kit.core import render
from autopost_kit.core.images import ImageFetcher
from autopost_kit.core.models import Item, Slide
from autopost_kit.core.render import Theme, font


def _date_label(target: date) -> str:
    return f"{target:%b} {target.day}".upper()


def _top_bar(draw: ImageDraw.ImageDraw, theme: Theme, left: str, target: date, left_is_rank: bool) -> None:
    m = theme.margin
    if left_is_rank:
        draw.text((m, 10), left, font=font("display", 120), fill=theme.rgb("accent"))
    else:
        draw.text((m, 38), left, font=font("text", 34, "ExtraBold"), fill=theme.rgb("text"))
    label = _date_label(target)
    date_font = font("display", 56)
    draw.text((theme.width - m - render.text_width(label, date_font), 28), label, font=date_font,
              fill=theme.rgb("accent"))


def render_cover(theme: Theme, strings: dict[str, str], target: date, total: int, games: list[Item]) -> Slide:
    image = Image.new("RGB", theme.size, theme.rgb("background"))
    draw = ImageDraw.Draw(image)
    m = theme.margin
    _top_bar(draw, theme, strings["handle"], target, left_is_rank=False)

    title = font("display", 170)
    draw.text((m, 170), strings["cover_title_1"], font=title, fill=theme.rgb("text"))
    line2_y = 170 + 146
    draw.text((m, line2_y), strings["cover_title_2a"], font=title, fill=theme.rgb("text"))
    offset = render.text_width(strings["cover_title_2a"], title)
    draw.text((m + offset, line2_y), strings["cover_title_2b"], font=title, fill=theme.rgb("accent"))

    strong = strings["cover_count_strong"].format(total=total)
    rest = strings["cover_count_rest"].format(count=len(games))
    count_y = line2_y + 190
    draw.text((m, count_y), strong, font=font("text", 46, "Bold"), fill=theme.rgb("text"))
    draw.text((m + render.text_width(strong, font("text", 46, "Bold")), count_y), rest,
              font=font("text", 46, "SemiBold"), fill=theme.rgb("muted"))

    top = count_y + 100
    draw.rectangle((m, top, theme.width - m, top + 4), fill=theme.rgb("accent"))
    row_h = 104
    number_font, name_font, genre_font = font("display", 72), font("text", 44, "ExtraBold"), font("text", 32)
    for i, game in enumerate(games):
        y = top + 24 + i * row_h
        draw.text((m, y), str(i + 1), font=number_font, fill=theme.rgb("accent"))
        genres = " · ".join(game.meta.get("display_genres", [])[:2])
        genre_w = render.text_width(genres, genre_font)
        draw.text((theme.width - m - genre_w, y + 28), genres, font=genre_font, fill=theme.rgb("muted"))
        name_max = theme.width - m - genre_w - 40 - (m + 88)
        draw.text((m + 88, y + 16), render.truncate(game.title, name_font, name_max), font=name_font,
                  fill=theme.rgb("text"))
        line_y = y + row_h - 20
        draw.rectangle((m, line_y, theme.width - m, line_y + 2), fill=theme.rgb("divider"))

    swipe_font = font("text", 34, "SemiBold")
    swipe = strings["swipe"]
    draw.text((theme.width - m - render.text_width(swipe, swipe_font), theme.height - 90), swipe,
              font=swipe_font, fill=theme.rgb("muted"))
    return Slide(label="cover", image=image)


def render_game(theme: Theme, strings: dict[str, str], target: date, game: Item, rank: int,
                fetch: ImageFetcher) -> Slide:
    bg = theme.rgb("background")
    image = Image.new("RGBA", theme.size, bg + (255,))

    screenshot = fetch(game.meta.get("screenshot")) or fetch(game.image_url)
    if screenshot is not None:
        image.paste(render.cover_crop(screenshot, theme.width, 900), (0, 0))
    fade = render.vertical_fade(theme.width, theme.height, bg,
                                [(0.0, 0.55), (0.18, 0.0), (0.40, 0.0), (0.66, 1.0), (1.0, 1.0)])
    image.alpha_composite(fade)
    draw = ImageDraw.Draw(image)
    m = theme.margin
    _top_bar(draw, theme, f"#{rank}", target, left_is_rank=True)

    # Build the info block bottom-up so it always sits just above the footer.
    max_w = theme.width - 2 * m
    title_font, title_lines = render.fit_lines(game.title.upper(), "display", max_w, (150, 130, 110, 96))
    title_line_h = round(title_font.size * 0.92)
    genres = " · ".join(game.meta.get("display_genres", [])[:3])
    studio = ", ".join(game.meta.get("developers", [])[:2])
    badge = game.meta.get("badge")
    meta_font = font("text", 42, "SemiBold")
    studio_font = font("text", 42, "Bold")
    badge_font = font("text", 38, "ExtraBold")

    header = fetch(game.image_url) if game.meta.get("screenshot") else None
    header_h = 0
    if header is not None:
        header = header.convert("RGB")
        header_w = 420
        header_h = round(header.height * header_w / header.width)
        header = render.rounded(header.resize((header_w, header_h), Image.LANCZOS), 10)

    heights = [
        header_h + 34 if header is not None else 0,
        title_line_h * len(title_lines),
        22 + 50 if genres else 0,
        8 + 50 if studio else 0,
        30 + 66 if badge else 0,
    ]
    y = theme.height - 120 - sum(heights)

    if header is not None:
        image.alpha_composite(header, (m, y))
        y += heights[0]
    for line in title_lines:
        draw.text((m, y), line, font=title_font, fill=theme.rgb("text"))
        y += title_line_h
    if genres:
        y += 22
        draw.text((m, y), genres, font=meta_font, fill=theme.rgb("muted"))
        y += 50
    if studio:
        y += 8
        prefix = strings["by_studio"]
        draw.text((m, y), prefix, font=meta_font, fill=theme.rgb("muted"))
        studio_x = m + render.text_width(prefix, meta_font) + 4
        draw.text((studio_x, y), render.truncate(studio, studio_font, max_w - studio_x + m), font=studio_font,
                  fill=theme.rgb("text"))
        y += 50
    if badge:
        y += 30
        render.pill(draw, (m, y), badge, badge_font, theme.rgb("accent"), theme.rgb("on_accent"))

    footer_font = font("text", 30, "SemiBold")
    draw.text((m, theme.height - 80), strings["footer"], font=footer_font, fill=theme.rgb("muted"))
    return Slide(label=f"#{rank}", image=image.convert("RGB"))
