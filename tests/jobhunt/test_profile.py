from pathlib import Path

import pytest

from jobhunt.profile import ProfileError, load_profile, parse_profile


def minimal(**overrides):
    data = {"resume": "master.yaml", "search": {"terms": ["java"]}}
    data.update(overrides)
    return data


def test_template_is_valid(data_dir):
    profile = load_profile(data_dir / "profile.yaml")

    assert profile.resume == data_dir / "master.yaml"
    assert "glassdoor" in profile.search.sites
    assert profile.filters.min_salary == 12000
    assert profile.skills[0].name == "Java"


def test_defaults():
    profile = parse_profile(minimal())

    assert profile.search.sites == ("linkedin", "indeed", "glassdoor", "gupy")
    assert profile.filters.seniority == ()
    assert profile.answers == ()


def test_relative_resume_follows_the_profile_and_absolute_is_kept(tmp_path):
    assert parse_profile(minimal(), base=tmp_path).resume == tmp_path / "master.yaml"

    absolute = tmp_path / "elsewhere" / "cv.yaml"
    assert parse_profile(minimal(resume=str(absolute)), base=Path("x")).resume == absolute


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (minimal(search={}), r"search\.terms: campo obrigatório"),
        (minimal(search={"terms": []}), r"search\.terms: a lista não pode ficar vazia"),
        (minimal(search={"terms": ["java"], "termz": 1}), r"search\.termz: campo desconhecido"),
        (
            minimal(search={"terms": ["java"], "sites": ["catho"]}),
            r"search\.sites\[0\]: use 'linkedin', 'indeed', 'glassdoor' ou 'gupy'",
        ),
        (minimal(search={"terms": ["java"], "hours_old": 0}), r"search\.hours_old: deve ser pelo"),
        (minimal(filters={"pj_factor": "muito"}), r"filters\.pj_factor: esperado um número"),
        (minimal(skills=[{"name": "Java"}]), r"skills\[0\]\.years: campo obrigatório"),
        (minimal(answers=[{"question": " ", "answer": "x"}]), r"answers\[0\]\.question: texto"),
        (None, r"raiz: esperado um objeto"),
    ],
)
def test_errors_point_to_the_field(data, message):
    with pytest.raises(ProfileError, match=message):
        parse_profile(data)


def test_every_error_is_reported():
    with pytest.raises(ProfileError) as error:
        parse_profile({"search": {"terms": ["java"], "remote_only": "talvez"}})

    assert "resume: campo obrigatório" in str(error.value)
    assert "search.remote_only: use true ou false" in str(error.value)


def test_numbers_are_accepted_as_text():
    profile = parse_profile(minimal(answers=[{"question": "Pretensão?", "answer": 14000}]))

    assert profile.answers[0].answer == "14000"


def test_unreadable_file_reports_the_path(tmp_path):
    with pytest.raises(ProfileError, match="não foi possível ler"):
        load_profile(tmp_path / "nao-existe.yaml")


def test_invalid_yaml(tmp_path):
    path = tmp_path / "profile.yaml"
    path.write_text("search: [", encoding="utf-8")

    with pytest.raises(ProfileError, match="YAML inválido"):
        load_profile(path)
