"""Per-language strings with ``{token}`` placeholders.

Each topic keeps a ``locales/<lang>.yaml`` file. Templates are filled with
:func:`fill`; an unknown token raises, so typos never reach a published post.
"""

from __future__ import annotations

from importlib import resources
from typing import Any

import yaml


def load_strings(package: str, language: str = "en") -> dict[str, str]:
    text = resources.files(package).joinpath("locales", f"{language}.yaml").read_text("utf-8")
    return yaml.safe_load(text) or {}


def fill(template: str, **tokens: Any) -> str:
    return template.format(**tokens)
