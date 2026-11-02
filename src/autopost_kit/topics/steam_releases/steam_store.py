"""Thin wrapper over the public Steam store endpoints used by this topic.

These are the same endpoints the store website calls. They are not an official,
documented API, so the wrapper keeps requests slow and the parsing defensive.
"""

from __future__ import annotations

from typing import Any

from autopost_kit.core.http import PoliteClient
from autopost_kit.topics.steam_releases.parsing import SearchRow, parse_search_html

BASE = "https://store.steampowered.com"
#: Store search category for full games (leaves out soundtracks, demos, DLC...).
GAMES_CATEGORY = "998"


class SteamStore:
    def __init__(self, client: PoliteClient, country: str = "us", language: str = "english") -> None:
        self.client = client
        self.country = country
        self.language = language

    def search(
        self,
        filter_: str,
        start: int = 0,
        count: int = 100,
        sort_by: str | None = None,
        category: str | None = None,
    ) -> tuple[list[SearchRow], int]:
        """One page of store search. Returns (rows, total_count).

        Steam may return fewer rows than ``count`` (often 25), so callers should
        advance ``start`` by the number of rows actually received.
        """
        params: dict[str, Any] = {
            "filter": filter_,
            "infinite": 1,
            "start": start,
            "count": count,
            "cc": self.country,
            "l": self.language,
            "ignore_preferences": 1,
        }
        if sort_by:
            params["sort_by"] = sort_by
        if category:
            params["category1"] = category
        data = self.client.get_json(f"{BASE}/search/results/", params=params)
        rows = parse_search_html(data.get("results_html") or "")
        return rows, int(data.get("total_count") or 0)

    def app_details(self, appid: str) -> dict[str, Any] | None:
        """Store details for one app, or ``None`` if Steam has none."""
        params = {"appids": appid, "cc": self.country, "l": self.language}
        data = self.client.get_json(f"{BASE}/api/appdetails", params=params)
        entry = (data or {}).get(str(appid)) or {}
        return entry.get("data") if entry.get("success") else None
