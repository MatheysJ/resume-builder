from dataclasses import replace
from pathlib import Path

import pytest

from resume_builder import PROJECT_URL
from resume_builder.model import Basics, Link, parse_resume
from resume_builder.render import contact_items, render_html
from resume_builder.theming import ThemeError, available_themes, load_theme


def test_html_has_content_metadata_and_font_size(example):
    html = render_html(example, load_theme("classic"), 10.25)

    assert "<title>Currículo · Ana Souza</title>" in html
    assert '<meta name="author" content="Ana Souza">' in html
    assert '<html lang="pt-BR">' in html
    assert "--font-size: 10.25pt" in html
    assert "<strong>4 h para 35 min</strong>" in html


def test_main_column_comes_before_the_sidebar(example):
    html = render_html(example, load_theme("sidebar"), 10)

    sidebar = html.index('<aside class="layout__side">')
    assert html.index("Experiência") < sidebar < html.index("Competências")


def test_contact_line_links_and_escapes():
    basics = Basics(
        name="Ana",
        location="São Paulo <SP>",
        email="ana@example.com",
        phone="+55 (11) 90000-0000",
        links=(Link("site", "https://ana.dev"), Link("ruim", "javascript:alert(1)")),
    )

    items = [str(item) for item in contact_items(basics)]

    assert items == [
        "São Paulo &lt;SP&gt;",
        '<a href="mailto:ana@example.com">ana@example.com</a>',
        '<a href="tel:+5511900000000">+55 (11) 90000-0000</a>',
        '<a href="https://ana.dev">site</a>',
        "ruim",
    ]


def test_builtin_themes_hide_the_base():
    assert available_themes() == ["classic", "minimal", "sidebar"]
    with pytest.raises(ThemeError):
        load_theme("_base")


def test_every_theme_includes_the_base(tmp_path: Path):
    custom = tmp_path / "meu.css"
    custom.write_text(".header__name { color: red; }", encoding="utf-8")

    for css in (load_theme("minimal"), load_theme(str(custom))):
        assert "@page" in css

    with pytest.raises(ThemeError, match="Disponíveis"):
        load_theme("inexistente")
    with pytest.raises(ThemeError):
        load_theme(str(tmp_path / "nao-existe.css"))


def test_credit_links_to_the_project(example):
    html = render_html(example, load_theme("classic"), 10)
    hidden = render_html(replace(example, credit=False), load_theme("classic"), 10)

    assert f'<a href="{PROJECT_URL}">@MatheysJ/resume-builder</a>' in html
    assert "resume-builder" not in hidden.split("</head>")[1]


def test_credit_and_default_title_follow_the_language():
    resume = parse_resume({"basics": {"name": "Ana"}, "meta": {"lang": "en-US"}})

    html = render_html(resume, load_theme("classic"), 10)

    assert resume.meta.title == "Resume · Ana"
    assert "This PDF was generated from YAML and CSS with" in html
