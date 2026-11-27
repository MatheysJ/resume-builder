from jobhunt.cli import EXIT_INVALID_INPUT, EXIT_OK, main


def test_init_creates_profile_and_database(tmp_path, capsys):
    data = tmp_path / "data"

    assert main(["--data", str(data), "init"]) == EXIT_OK
    assert (data / "profile.yaml").read_text(encoding="utf-8").startswith("# Perfil do jobhunt")
    assert (data / "jobhunt.db").exists()
    assert "criado:" in capsys.readouterr().out


def test_init_never_overwrites_the_profile(data_dir, capsys):
    profile = data_dir / "profile.yaml"
    profile.write_text("meu perfil", encoding="utf-8")

    assert main(["--data", str(data_dir), "init"]) == EXIT_OK
    assert profile.read_text(encoding="utf-8") == "meu perfil"
    assert "não foi alterado" in capsys.readouterr().out


def test_check_summarizes_profile_and_master_resume(data_dir, capsys):
    assert main(["--data", str(data_dir), "check"]) == EXIT_OK

    out = capsys.readouterr().out
    assert "perfil ok · 2 termos de busca" in out
    assert "currículo mestre ok" in out
    assert "bullets" in out


def test_check_without_profile_suggests_init(tmp_path, capsys):
    assert main(["--data", str(tmp_path), "check"]) == EXIT_INVALID_INPUT
    assert "jobhunt init" in capsys.readouterr().err


def test_check_reports_an_invalid_master_resume(data_dir, capsys):
    (data_dir / "master.yaml").write_text("basics: {}", encoding="utf-8")

    assert main(["--data", str(data_dir), "check"]) == EXIT_INVALID_INPUT
    assert "basics.name: campo obrigatório" in capsys.readouterr().err
