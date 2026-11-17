from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, get_args

import yaml

from resume_builder.labels import DEFAULT_LANG, labels

SectionKind = Literal["entries", "skills", "list", "text"]
Column = Literal["main", "side"]

SECTION_KINDS: tuple[str, ...] = get_args(SectionKind)
COLUMNS: tuple[str, ...] = get_args(Column)

ROOT_KEYS = ("meta", "basics", "summary", "sections", "credit")
META_KEYS = ("title", "author", "subject", "keywords", "lang")
BASICS_KEYS = ("name", "headline", "location", "email", "phone", "links")
LINK_KEYS = ("label", "url")
SECTION_KEYS = ("title", "kind", "column")
ENTRY_KEYS = ("title", "org", "period", "location", "text", "bullets")
SKILL_KEYS = ("label", "value")


class ResumeError(ValueError):
    pass


@dataclass(frozen=True)
class Link:
    label: str
    url: str


@dataclass(frozen=True)
class Basics:
    name: str
    headline: str = ""
    location: str = ""
    email: str = ""
    phone: str = ""
    links: tuple[Link, ...] = ()


@dataclass(frozen=True)
class Meta:
    title: str
    author: str
    subject: str = ""
    keywords: tuple[str, ...] = ()
    lang: str = DEFAULT_LANG


@dataclass(frozen=True)
class Entry:
    title: str
    org: str = ""
    period: str = ""
    location: str = ""
    text: str = ""
    bullets: tuple[str, ...] = ()


@dataclass(frozen=True)
class Skill:
    label: str
    value: str


@dataclass(frozen=True)
class Section:
    title: str
    kind: SectionKind
    column: Column = "main"
    entries: tuple[Entry, ...] = ()
    skills: tuple[Skill, ...] = ()
    items: tuple[str, ...] = ()
    text: str = ""


@dataclass(frozen=True)
class Resume:
    meta: Meta
    basics: Basics
    summary: str = ""
    sections: tuple[Section, ...] = ()
    credit: bool = True

    def column(self, column: Column) -> tuple[Section, ...]:
        return tuple(s for s in self.sections if s.column == column)


def load_resume(path: str | Path) -> Resume:
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ResumeError(f"{path}: não foi possível ler o arquivo ({error.strerror})") from error
    except UnicodeDecodeError as error:
        raise ResumeError(f"{path}: o arquivo precisa estar em UTF-8") from error
    except yaml.YAMLError as error:
        raise ResumeError(f"{path}: YAML inválido: {error}") from error
    return parse_resume(data)


def parse_resume(data: Any) -> Resume:
    root = _object(data, "", ROOT_KEYS)
    basics = _basics(_object(root.get("basics"), "basics", BASICS_KEYS))
    meta = _meta(_object(_get(root, "meta", {}), "meta", META_KEYS), basics)
    sections = tuple(
        _section(item, f"sections[{i}]")
        for i, item in enumerate(_sequence(_get(root, "sections", []), "sections"))
    )
    return Resume(
        meta=meta,
        basics=basics,
        summary=_optional_str(root, "summary", ""),
        sections=sections,
        credit=_bool(root, "credit", default=True),
    )


def _basics(data: dict[str, Any]) -> Basics:
    links = tuple(
        Link(
            label=_required_str(link, "label", path),
            url=_required_str(link, "url", path),
        )
        for path, link in _objects(_get(data, "links", []), "basics.links", LINK_KEYS)
    )
    return Basics(
        name=_required_str(data, "name", "basics"),
        headline=_optional_str(data, "headline", "basics"),
        location=_optional_str(data, "location", "basics"),
        email=_optional_str(data, "email", "basics"),
        phone=_optional_str(data, "phone", "basics"),
        links=links,
    )


def _meta(data: dict[str, Any], basics: Basics) -> Meta:
    lang = _optional_str(data, "lang", "meta") or DEFAULT_LANG
    return Meta(
        title=_optional_str(data, "title", "meta") or f"{labels(lang)['title']} · {basics.name}",
        author=_optional_str(data, "author", "meta") or basics.name,
        subject=_optional_str(data, "subject", "meta"),
        keywords=_str_list(_get(data, "keywords", []), "meta.keywords"),
        lang=lang,
    )


def _section(data: Any, path: str) -> Section:
    raw = _object(data, path)
    kind = _get(raw, "kind", "entries")
    if kind not in SECTION_KINDS:
        raise ResumeError(f"{path}.kind: use um de {', '.join(SECTION_KINDS)}")
    column = _get(raw, "column", "main")
    if column not in COLUMNS:
        raise ResumeError(f"{path}.column: use um de {', '.join(COLUMNS)}")

    content_key = "text" if kind == "text" else "items"
    section = _object(raw, path, (*SECTION_KEYS, content_key))
    title = _required_str(section, "title", path)

    if kind == "text":
        return Section(title, kind, column, text=_required_str(section, "text", path))

    items_path = f"{path}.items"
    raw_items = _get(section, "items", [])
    if kind == "entries":
        entries = tuple(
            _entry(item, item_path)
            for item_path, item in _objects(raw_items, items_path, ENTRY_KEYS)
        )
        return Section(title, kind, column, entries=entries)
    if kind == "skills":
        skills = tuple(
            Skill(
                label=_required_str(item, "label", item_path),
                value=_required_str(item, "value", item_path),
            )
            for item_path, item in _objects(raw_items, items_path, SKILL_KEYS)
        )
        return Section(title, kind, column, skills=skills)
    return Section(title, kind, column, items=_str_list(raw_items, items_path))


def _entry(data: dict[str, Any], path: str) -> Entry:
    return Entry(
        title=_required_str(data, "title", path),
        org=_optional_str(data, "org", path),
        period=_optional_str(data, "period", path),
        location=_optional_str(data, "location", path),
        text=_optional_str(data, "text", path),
        bullets=_str_list(_get(data, "bullets", []), f"{path}.bullets"),
    )


def _join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _get(data: dict[str, Any], key: str, default: Any) -> Any:
    value = data.get(key)
    return default if value is None else value


def _object(value: Any, path: str, allowed: tuple[str, ...] | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ResumeError(f"{path or 'raiz'}: esperado um objeto (chave: valor)")
    unknown = [key for key in value if allowed is not None and key not in allowed]
    if unknown:
        raise ResumeError(
            f"{_join(path, str(unknown[0]))}: campo desconhecido (use: {', '.join(allowed)})"
        )
    return value


def _sequence(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ResumeError(f"{path}: esperada uma lista")
    return value


def _objects(value: Any, path: str, allowed: tuple[str, ...]) -> list[tuple[str, dict[str, Any]]]:
    return [
        (f"{path}[{i}]", _object(item, f"{path}[{i}]", allowed))
        for i, item in enumerate(_sequence(value, path))
    ]


def _bool(data: dict[str, Any], key: str, *, default: bool) -> bool:
    value = _get(data, key, default)
    if not isinstance(value, bool):
        raise ResumeError(f"{key}: use true ou false")
    return value


def _text(value: Any, path: str) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if not isinstance(value, str):
        raise ResumeError(f"{path}: esperado um texto")
    return value.strip()


def _optional_str(data: dict[str, Any], key: str, path: str) -> str:
    return _text(_get(data, key, ""), _join(path, key))


def _required_str(data: dict[str, Any], key: str, path: str) -> str:
    value = _optional_str(data, key, path)
    if not value:
        raise ResumeError(f"{_join(path, key)}: campo obrigatório")
    return value


def _str_list(value: Any, path: str) -> tuple[str, ...]:
    items = tuple(_text(item, f"{path}[{i}]") for i, item in enumerate(_sequence(value, path)))
    for i, item in enumerate(items):
        if not item:
            raise ResumeError(f"{path}[{i}]: texto vazio")
    return items
