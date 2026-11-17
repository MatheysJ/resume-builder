from __future__ import annotations

from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path

BASE_THEME = "_base"


class ThemeError(ValueError):
    pass


def _themes_dir() -> Traversable:
    return resources.files("resume_builder") / "themes"


def _builtin(name: str) -> str | None:
    css = _themes_dir() / f"{name}.css"
    return css.read_text(encoding="utf-8") if css.is_file() else None


def available_themes() -> list[str]:
    return sorted(
        Path(entry.name).stem
        for entry in _themes_dir().iterdir()
        if entry.name.endswith(".css") and not entry.name.startswith("_")
    )


def load_theme(name_or_path: str) -> str:
    path = Path(name_or_path)
    if path.suffix.lower() == ".css":
        if not path.is_file():
            raise ThemeError(f"Tema não encontrado: {path}")
        theme = path.read_text(encoding="utf-8")
    else:
        theme = None if name_or_path.startswith("_") else _builtin(name_or_path)
        if theme is None:
            options = ", ".join(available_themes())
            raise ThemeError(f"Tema '{name_or_path}' não existe. Disponíveis: {options}")

    return f"{_builtin(BASE_THEME)}\n\n{theme}"
