"""Turn Steam store responses into plain Python data.

The store search endpoint returns JSON with an HTML fragment (``results_html``),
one ``<a class="search_result_row">`` per game. The standard library HTML parser
is enough to read it, so no extra dependency is needed.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from html.parser import HTMLParser

_DATE_FORMATS = ("%b %d, %Y", "%d %b, %Y", "%B %d, %Y", "%d %B, %Y")


def parse_release_date(text: str | None) -> date | None:
    """Parse an exact Steam release date such as ``Nov 3, 2026``.

    Vague values ("Coming soon", "Q4 2026", "November 2026", "To be announced")
    return ``None``: they cannot be placed on a specific day.
    """
    if not text:
        return None
    cleaned = " ".join(text.replace("\xa0", " ").split())
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


@dataclass
class SearchRow:
    appid: str
    title: str
    url: str
    release_text: str
    capsule_url: str | None = None
    content_descriptors: list[int] = field(default_factory=list)

    @property
    def release_date(self) -> date | None:
        return parse_release_date(self.release_text)


def _int_list(raw: str | None) -> list[int]:
    if not raw:
        return []
    try:
        return [int(v) for v in json.loads(raw)]
    except (ValueError, TypeError):
        return [int(v) for v in re.findall(r"\d+", raw)]


class _SearchResultsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[SearchRow] = []
        self._row: SearchRow | None = None
        self._capture: str | None = None  # "title" | "release" | None
        self._depth = 0  # div depth inside the release block

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        classes = (a.get("class") or "").split()

        if tag == "a" and "search_result_row" in classes and a.get("data-ds-appid"):
            href = (a.get("href") or "").split("?")[0]
            self._row = SearchRow(
                appid=a["data-ds-appid"] or "",
                title="",
                url=href,
                release_text="",
                content_descriptors=_int_list(a.get("data-ds-descids")),
            )
            return
        if self._row is None:
            return

        if tag == "img" and self._row.capsule_url is None:
            self._row.capsule_url = a.get("src")
        elif tag == "span" and "title" in classes:
            self._capture = "title"
        elif tag == "div" and "search_released" in classes:
            self._capture = "release"
            self._depth = 1
        elif tag == "div" and self._capture == "release":
            self._depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self._row is None:
            return
        if tag == "span" and self._capture == "title":
            self._capture = None
        elif tag == "div" and self._capture == "release":
            self._depth -= 1
            if self._depth == 0:
                self._capture = None
        elif tag == "a":
            self._row.title = self._row.title.strip()
            self._row.release_text = " ".join(self._row.release_text.split())
            self.rows.append(self._row)
            self._row = None
            self._capture = None

    def handle_data(self, data: str) -> None:
        if self._row is None:
            return
        if self._capture == "title":
            self._row.title += data
        elif self._capture == "release":
            self._row.release_text += data


def parse_search_html(html: str) -> list[SearchRow]:
    parser = _SearchResultsParser()
    parser.feed(html)
    parser.close()
    return parser.rows
