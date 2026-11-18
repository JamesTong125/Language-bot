"""Versioned prompt files. Load them by name, e.g. ``load_prompt("partner_reply_v1")``.

Prompts use ``$name`` placeholders (string.Template), so JSON braces need no escaping.
"""

from functools import cache
from pathlib import Path
from string import Template

_DIR = Path(__file__).parent


@cache
def load_prompt(name: str) -> Template:
    return Template((_DIR / f"{name}.md").read_text(encoding="utf-8"))


def render_prompt(name: str, **values: str) -> str:
    """Fill every placeholder. A missing value raises KeyError instead of leaking ``$x``."""
    return load_prompt(name).substitute(values).strip()
