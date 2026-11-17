from __future__ import annotations

DEFAULT_LANG = "pt-BR"

_LABELS = {
    "pt": {
        "title": "Currículo",
        "credit": "Este PDF foi gerado a partir de YAML e CSS com",
    },
    "en": {
        "title": "Resume",
        "credit": "This PDF was generated from YAML and CSS with",
    },
}


def labels(lang: str) -> dict[str, str]:
    return _LABELS.get(lang.split("-")[0].lower(), _LABELS["en"])
