"""The contract every topic implements, plus config loading.

The core drives the pipeline (collect -> select -> build post -> review -> publish);
a topic only answers "where does the data come from", "what goes in the post"
and "what should the post look like".
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from importlib import resources
from typing import Any

import yaml

from autopost_kit.core.models import Item, Post


def deep_merge(base: dict[str, Any], changes: dict[str, Any]) -> dict[str, Any]:
    """``base`` with ``changes`` applied; nested dicts are merged, not replaced."""
    merged = dict(base)
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


class Topic(ABC):
    """Base class for a subject the engine can post about."""

    #: Unique id used on the command line, e.g. ``steam_releases``.
    name: str = ""
    #: Package that holds this topic's ``topic.yaml`` and ``locales/``.
    config_package: str = ""

    def __init__(self, overrides: dict[str, Any] | None = None) -> None:
        self.config = self.load_config(overrides)

    @classmethod
    def load_config(cls, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        config: dict[str, Any] = {}
        if cls.config_package:
            text = resources.files(cls.config_package).joinpath("topic.yaml").read_text("utf-8")
            config = yaml.safe_load(text) or {}
        return deep_merge(config, overrides or {})

    @abstractmethod
    def target_date(self) -> date:
        """The day this topic posts about when run now."""

    @abstractmethod
    def collect(self, target: date) -> list[Item]:
        """Fetch every candidate item for ``target``."""

    def select(self, items: list[Item]) -> list[Item]:
        """Pick what goes into the post. Default: everything, in order."""
        return items

    @abstractmethod
    def build_post(self, target: date, selected: list[Item], total: int) -> Post:
        """Turn the selected items into slides and a caption.

        ``total`` is how many candidates were collected before selection.
        """
