from __future__ import annotations

import argparse
import sys
from contextlib import closing
from importlib.resources import files
from pathlib import Path

from jobhunt import db
from jobhunt.profile import ProfileError, load_profile
from resume_builder.model import ResumeError, load_resume

EXIT_OK = 0
EXIT_INVALID_INPUT = 1

PROFILE_FILE = "profile.yaml"
DATABASE_FILE = "jobhunt.db"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jobhunt",
        description="Busca vagas e prepara candidaturas a partir do seu currículo mestre.",
    )
    parser.add_argument(
        "-d", "--data", type=Path, default=Path("data"),
        help="pasta do perfil e do banco, fora do Git (padrão: data)",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="cria o perfil de exemplo e o banco")
    commands.add_parser("check", help="valida o perfil e o currículo mestre")
    return parser


def _count(number: int, singular: str, plural: str) -> str:
    return f"{number} {singular if number == 1 else plural}"


def _init(data: Path) -> int:
    data.mkdir(parents=True, exist_ok=True)
    profile = data / PROFILE_FILE
    if profile.exists():
        print(f"{profile} já existe e não foi alterado")
    else:
        template = files("jobhunt").joinpath("templates", PROFILE_FILE)
        profile.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"criado: {profile}")

    with closing(db.connect(data / DATABASE_FILE)):
        print(f"banco: {data / DATABASE_FILE}")
    print(f"próximo passo: edite {profile}, aponte `resume` para o seu currículo mestre "
          "e rode `jobhunt check`")
    return EXIT_OK


def _check(data: Path) -> int:
    path = data / PROFILE_FILE
    if not path.exists():
        raise ProfileError(f"{path} não existe; rode `jobhunt init` primeiro")
    profile = load_profile(path)
    resume = load_resume(profile.resume)

    entries = [entry for section in resume.sections for entry in section.entries]
    bullets = sum(len(entry.bullets) for entry in entries)
    search = profile.search
    print(
        f"perfil ok · {_count(len(search.terms), 'termo', 'termos')} de busca"
        f" · sites: {', '.join(search.sites)}"
        f" · {_count(len(profile.skills), 'competência', 'competências')}"
        f" · {_count(len(profile.answers), 'resposta salva', 'respostas salvas')}"
    )
    print(
        f"currículo mestre ok · {profile.resume}"
        f" · {_count(len(resume.sections), 'seção', 'seções')}"
        f" · {_count(len(entries), 'item', 'itens')}"
        f" · {_count(bullets, 'bullet', 'bullets')}"
    )
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "init":
            return _init(args.data)
        return _check(args.data)
    except (ProfileError, ResumeError, db.DatabaseError) as error:
        print(f"erro: {error}", file=sys.stderr)
        return EXIT_INVALID_INPUT
