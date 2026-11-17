from __future__ import annotations

import re

from markupsafe import Markup, escape

ALLOWED_SCHEMES = ("http://", "https://", "mailto:", "tel:")

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def is_safe_url(url: str) -> bool:
    return url.lower().startswith(ALLOWED_SCHEMES)


def _link(match: re.Match[str]) -> str:
    label, url = match.group(1), match.group(2)
    if not is_safe_url(url):
        return label
    return f'<a href="{url}">{label}</a>'


def inline(text: str) -> Markup:
    # Escaping must happen before the substitutions, which emit raw HTML.
    html = str(escape(text))
    html = _LINK.sub(_link, html)
    html = _BOLD.sub(r"<strong>\1</strong>", html)
    return Markup(html)
