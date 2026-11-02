"""Publish to Instagram through the official Graph API.

Uses the "Instagram API with Unified Login" setup: a business-portfolio system
user token on graph.facebook.com. Publishing is two steps: create a media
container (Instagram downloads the file from a URL), wait until it is
processed, then publish it.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

import requests

log = logging.getLogger(__name__)

HOST = "https://graph.facebook.com"


class InstagramError(RuntimeError):
    pass


class InstagramClient:
    def __init__(
        self,
        token: str,
        user_id: str | None = None,
        api_version: str = "v26.0",
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
        poll_seconds: float = 5.0,
    ) -> None:
        self.token = token
        self._user_id = user_id
        self._username: str | None = None
        self.base = f"{HOST}/{api_version}"
        self.session = session or requests.Session()
        self.sleep = sleep
        self.poll_seconds = poll_seconds

    # -- low level -----------------------------------------------------------

    def _call(self, method: str, path: str, **params: Any) -> dict[str, Any]:
        params["access_token"] = self.token
        kwargs = {"params": params} if method == "GET" else {"data": params}
        response = self.session.request(method, f"{self.base}/{path}", timeout=60, **kwargs)
        try:
            data = response.json()
        except ValueError:
            data = {}
        if response.status_code >= 400 or "error" in data:
            error = data.get("error", {})
            message = error.get("message") or response.text[:200]
            raise InstagramError(f"{method} {path}: {message} (HTTP {response.status_code})")
        return data

    # -- account -------------------------------------------------------------

    @property
    def user_id(self) -> str:
        if not self._user_id:
            accounts = self._call("GET", "me/assigned_instagram_accounts", fields="id,username").get("data") or []
            if not accounts:
                raise InstagramError("No Instagram account is shared with this token.")
            self._user_id = str(accounts[0]["id"])
            self._username = accounts[0].get("username")
        return self._user_id

    def account(self) -> dict[str, Any]:
        return self._call("GET", self.user_id, fields="id,username,media_count,followers_count")

    def publishing_quota(self) -> dict[str, Any]:
        data = self._call("GET", f"{self.user_id}/content_publishing_limit", fields="quota_usage,config")
        return (data.get("data") or [{}])[0]

    # -- containers ----------------------------------------------------------

    def create_reel(self, video_url: str, caption: str, share_to_feed: bool = True) -> str:
        return self._call(
            "POST", f"{self.user_id}/media",
            media_type="REELS", video_url=video_url, caption=caption, share_to_feed=str(share_to_feed).lower(),
        )["id"]

    def create_image(self, image_url: str, carousel_item: bool = False) -> str:
        params: dict[str, Any] = {"image_url": image_url}
        if carousel_item:
            params["is_carousel_item"] = "true"
        return self._call("POST", f"{self.user_id}/media", **params)["id"]

    def create_carousel(self, children: list[str], caption: str) -> str:
        return self._call(
            "POST", f"{self.user_id}/media", media_type="CAROUSEL", children=",".join(children), caption=caption
        )["id"]

    def status(self, container_id: str) -> dict[str, Any]:
        return self._call("GET", container_id, fields="status_code,status")

    def wait_until_ready(self, container_id: str, timeout: float = 600) -> None:
        waited = 0.0
        while True:
            info = self.status(container_id)
            code = info.get("status_code")
            if code == "FINISHED":
                return
            if code in {"ERROR", "EXPIRED"}:
                raise InstagramError(f"Instagram could not process the media: {info.get('status') or code}")
            if waited >= timeout:
                raise InstagramError(f"Media still {code} after {timeout:.0f}s.")
            log.info("Instagram is processing the media (%s)...", code)
            self.sleep(self.poll_seconds)
            waited += self.poll_seconds

    def publish(self, container_id: str) -> str:
        """Publish a ready container. Never retried blindly, to avoid posting twice."""
        try:
            return self._call("POST", f"{self.user_id}/media_publish", creation_id=container_id)["id"]
        except InstagramError:
            if self.status(container_id).get("status_code") == "PUBLISHED":
                latest = self._call("GET", f"{self.user_id}/media", fields="id", limit=1).get("data") or []
                if latest:
                    return latest[0]["id"]
            raise

    def permalink(self, media_id: str) -> str | None:
        return self._call("GET", media_id, fields="permalink").get("permalink")
