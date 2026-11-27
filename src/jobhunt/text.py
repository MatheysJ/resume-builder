from __future__ import annotations

import re
import unicodedata

_WORD = re.compile(r"[^\W_]+")


def normalize(text: str) -> str:
    """Lowercase, drop accents and keep only letters and digits, one space apart.

    Used to compare text typed by different people: company names, job titles,
    form questions. "Back-End Sênior" and "back end senior" become the same key.
    """
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(_WORD.findall(plain))
