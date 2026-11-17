import pytest

from resume_builder.cli import EXIT_INVALID_INPUT, main


def test_missing_resume_exits_with_invalid_input(tmp_path, capsys):
    code = main(["build", str(tmp_path / "nao-existe.yaml")])

    assert code == EXIT_INVALID_INPUT
    assert "erro:" in capsys.readouterr().err


@pytest.mark.parametrize(
    "args",
    [
        ["--pages", "0"],
        ["--min-size", "-1"],
        ["--min-size", "13", "--max-size", "12"],
    ],
)
def test_invalid_options_are_usage_errors(example_path, args):
    with pytest.raises(SystemExit) as exit_info:
        main(["build", str(example_path), *args])

    assert exit_info.value.code == 2
