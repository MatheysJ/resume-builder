"""Load and validate the profile: search terms, filters, skills and saved answers.

The career content itself (experience, bullets, education) lives in the master
resume, a regular resume-builder YAML that the profile points to.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

Site = Literal["linkedin", "indeed", "glassdoor", "gupy"]
Seniority = Literal["intern", "junior", "mid", "senior", "staff", "lead"]
WorkModel = Literal["remote", "hybrid", "onsite"]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ProfileError(ValueError):
    pass


class _Strict(BaseModel):
    # Unknown keys are errors, so a typo never disappears silently.
    model_config = ConfigDict(extra="forbid", frozen=True, coerce_numbers_to_str=True)


class Search(_Strict):
    terms: tuple[Text, ...] = Field(min_length=1)
    location: str = ""
    sites: tuple[Site, ...] = ("linkedin", "indeed", "glassdoor", "gupy")
    remote_only: bool = False
    hours_old: int = Field(72, ge=1)
    results_per_term: int = Field(30, ge=1, le=200)


class Filters(_Strict):
    seniority: tuple[Seniority, ...] = ()
    work_model: tuple[WorkModel, ...] = ()
    min_salary: float | None = Field(None, gt=0)
    pj_factor: float = Field(1.4, gt=0)
    exclude_companies: tuple[Text, ...] = ()
    exclude_terms: tuple[Text, ...] = ()


class Skill(_Strict):
    name: Text
    years: float = Field(ge=0)
    aliases: tuple[Text, ...] = ()


class Answer(_Strict):
    question: Text
    answer: Text


class Profile(_Strict):
    resume: Path
    search: Search
    filters: Filters = Field(default_factory=Filters)
    skills: tuple[Skill, ...] = ()
    answers: tuple[Answer, ...] = ()


def load_profile(path: str | Path) -> Profile:
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ProfileError(f"{path}: não foi possível ler o arquivo ({error.strerror})") from error
    except UnicodeDecodeError as error:
        raise ProfileError(f"{path}: o arquivo precisa estar em UTF-8") from error
    except yaml.YAMLError as error:
        raise ProfileError(f"{path}: YAML inválido: {error}") from error
    return parse_profile(data, base=path.parent, source=str(path))


def parse_profile(data: Any, *, base: Path = Path("."), source: str = "perfil") -> Profile:
    """Validate `data`; a relative `resume` path is resolved against `base`."""
    try:
        profile = Profile.model_validate(data)
    except ValidationError as error:
        details = "\n".join(f"  {_describe(item)}" for item in error.errors())
        raise ProfileError(f"{source}:\n{details}") from None
    return profile.model_copy(update={"resume": base / profile.resume})


_MESSAGES = {
    "missing": "campo obrigatório",
    "extra_forbidden": "campo desconhecido",
    "model_type": "esperado um objeto (chave: valor)",
    "dict_type": "esperado um objeto (chave: valor)",
    "list_type": "esperada uma lista",
    "tuple_type": "esperada uma lista",
    "too_short": "a lista não pode ficar vazia",
    "string_type": "esperado um texto",
    "string_too_short": "texto vazio",
    "bool_type": "use true ou false",
    "bool_parsing": "use true ou false",
    "int_type": "esperado um número inteiro",
    "int_parsing": "esperado um número inteiro",
    "int_from_float": "esperado um número inteiro",
    "float_type": "esperado um número",
    "float_parsing": "esperado um número",
    "path_type": "esperado um caminho de arquivo",
}

_BOUNDS = {
    "greater_than": ("gt", "maior que"),
    "greater_than_equal": ("ge", "pelo menos"),
    "less_than_equal": ("le", "no máximo"),
}


def _describe(error: Any) -> str:
    kind = error["type"]
    context = error.get("ctx", {})
    if kind == "literal_error":
        message = "use " + context["expected"].replace(" or ", " ou ")
    elif kind in _BOUNDS:
        key, words = _BOUNDS[kind]
        message = f"deve ser {words} {context[key]}"
    else:
        message = _MESSAGES.get(kind, error["msg"])
    return f"{_location(error['loc'])}: {message}"


def _location(parts: tuple[str | int, ...]) -> str:
    path = ""
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += f".{part}" if path else part
    return path or "raiz"
