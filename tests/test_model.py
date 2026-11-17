import pytest

from resume_builder.model import ResumeError, load_resume, parse_resume


def minimal(**overrides):
    data = {"basics": {"name": "Ana"}, "sections": []}
    data.update(overrides)
    return data


def test_example_loads(example):
    assert example.basics.name == "Ana Souza"
    assert [s.title for s in example.column("side")] == [
        "Competências",
        "Formação",
        "Idiomas e certificações",
    ]
    assert example.sections[0].entries[0].bullets


def test_meta_defaults_to_name():
    resume = parse_resume(minimal())

    assert resume.meta.title == "Currículo · Ana"
    assert resume.meta.author == "Ana"
    assert resume.credit is True


def test_required_name_reports_path():
    with pytest.raises(ResumeError, match=r"basics\.name"):
        parse_resume({"basics": {}})


def test_nested_error_reports_full_path():
    data = minimal(sections=[{"title": "Experiência", "items": [{"org": "X"}]}])

    with pytest.raises(ResumeError, match=r"sections\[0\]\.items\[0\]\.title"):
        parse_resume(data)


@pytest.mark.parametrize(
    ("section", "message"),
    [
        ({"title": "X", "kind": "tabela"}, r"sections\[0\]\.kind"),
        ({"title": "X", "column": "left"}, r"sections\[0\]\.column"),
        ({"title": "X", "kind": "list", "items": [{"a": 1}]}, r"sections\[0\]\.items\[0\]"),
        ({"title": "X", "kind": "text"}, r"sections\[0\]\.text"),
    ],
)
def test_invalid_sections(section, message):
    with pytest.raises(ResumeError, match=message):
        parse_resume(minimal(sections=[section]))


def test_numbers_are_accepted_as_text():
    data = minimal(sections=[{"title": "X", "items": [{"title": "Y", "period": 2024}]}])

    assert parse_resume(data).sections[0].entries[0].period == "2024"


def test_credit_can_be_turned_off():
    assert parse_resume(minimal(credit=False)).credit is False

    with pytest.raises(ResumeError, match="credit"):
        parse_resume(minimal(credit="não"))


def test_unknown_keys_are_rejected_with_their_path():
    data = minimal(sections=[{"title": "X", "items": [{"title": "Y", "bulets": ["a"]}]}])

    with pytest.raises(ResumeError, match=r"sections\[0\]\.items\[0\]\.bulets: campo desconhecido"):
        parse_resume(data)
    with pytest.raises(ResumeError, match=r"^sumary: campo desconhecido"):
        parse_resume(minimal(sumary="x"))


def test_text_sections_reject_items():
    with pytest.raises(ResumeError, match=r"sections\[0\]\.items"):
        parse_resume(minimal(sections=[{"title": "X", "kind": "text", "text": "a", "items": []}]))


def test_empty_values_are_treated_as_missing():
    resume = parse_resume(minimal(meta=None, sections=None, summary=None, credit=None))

    assert resume.sections == ()
    assert resume.summary == ""
    assert resume.credit is True


def test_numbers_are_accepted_in_lists():
    resume = parse_resume(minimal(meta={"keywords": ["Java", 2024]}))

    assert resume.meta.keywords == ("Java", "2024")


def test_missing_file_is_a_resume_error(tmp_path):
    with pytest.raises(ResumeError, match="não foi possível ler"):
        load_resume(tmp_path / "nao-existe.yaml")
