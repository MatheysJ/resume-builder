from __future__ import annotations

import re

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape
from markupsafe import Markup, escape

from resume_builder import PROJECT_HANDLE, PROJECT_URL
from resume_builder.labels import labels
from resume_builder.markup import inline, is_safe_url
from resume_builder.model import Basics, Resume

_env = Environment(
    loader=PackageLoader("resume_builder", "templates"),
    autoescape=select_autoescape(["html", "j2"]),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)
_env.filters["inline"] = inline


def font_size_css(font_size: float) -> str:
    return f":root {{ --font-size: {font_size:.2f}pt; }}"


def _anchor(url: str, label: str) -> Markup:
    if not is_safe_url(url):
        return escape(label)
    return Markup('<a href="{}">{}</a>').format(url, label)


def contact_items(basics: Basics) -> list[Markup]:
    items: list[Markup] = []
    if basics.location:
        items.append(escape(basics.location))
    if basics.email:
        items.append(_anchor(f"mailto:{basics.email}", basics.email))
    if basics.phone:
        digits = re.sub(r"[^\d+]", "", basics.phone)
        items.append(_anchor(f"tel:{digits}", basics.phone))
    items.extend(_anchor(link.url, link.label) for link in basics.links)
    return items


def render_html(resume: Resume, theme_css: str, font_size: float) -> str:
    template = _env.get_template("resume.html.j2")
    return template.render(
        resume=resume,
        main=resume.column("main"),
        side=resume.column("side"),
        contact=contact_items(resume.basics),
        theme_css=theme_css,
        size_css=font_size_css(font_size),
        credit={
            "text": labels(resume.meta.lang)["credit"],
            "handle": PROJECT_HANDLE,
            "url": PROJECT_URL,
        },
    )
