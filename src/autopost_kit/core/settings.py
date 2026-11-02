"""Secrets and environment settings, read from the environment or a local ``.env``.

Nothing secret is ever stored in the repository: see ``.env.example``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class MissingSetting(SystemExit):
    pass


def load_env(path: str | Path = ".env") -> None:
    """Load ``.env`` into the environment without overriding real variables."""
    load_dotenv(path, override=False)


def require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise MissingSetting(f"{name} is not set. Add it to your .env file (see .env.example).")
    return value


@dataclass(frozen=True)
class InstagramSettings:
    access_token: str
    user_id: str | None
    api_version: str

    @classmethod
    def from_env(cls) -> "InstagramSettings":
        return cls(
            access_token=require("INSTAGRAM_ACCESS_TOKEN"),
            user_id=os.environ.get("INSTAGRAM_USER_ID", "").strip() or None,
            api_version=os.environ.get("INSTAGRAM_API_VERSION", "").strip() or "v26.0",
        )


@dataclass(frozen=True)
class S3Settings:
    bucket: str
    region: str

    @classmethod
    def from_env(cls) -> "S3Settings":
        require("AWS_ACCESS_KEY_ID")
        require("AWS_SECRET_ACCESS_KEY")
        return cls(bucket=require("AUTOPOST_S3_BUCKET"), region=require("AWS_REGION"))
