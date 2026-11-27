import pytest

from jobhunt.text import normalize


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Back-End Sênior", "back end senior"),
        ("  Qual a sua PRETENSÃO salarial?  ", "qual a sua pretensao salarial"),
        ("Itaú_Unibanco / São Paulo", "itau unibanco sao paulo"),
        ("Java 17+", "java 17"),
        ("", ""),
    ],
)
def test_normalize(text, expected):
    assert normalize(text) == expected
