from __future__ import annotations

import argparse
import sys
from pathlib import Path

from resume_builder.model import ResumeError, load_resume
from resume_builder.theming import ThemeError, available_themes, load_theme

EXIT_OK = 0
EXIT_INVALID_INPUT = 1
EXIT_DOES_NOT_FIT = 3


def _positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("deve ser pelo menos 1")
    return number


def _positive_float(value: str) -> float:
    number = float(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("deve ser maior que zero")
    return number


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="resume-builder",
        description="Gera um currículo em PDF a partir de um arquivo YAML.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build", help="gera o PDF")
    build.add_argument("resume", type=Path, help="arquivo YAML do currículo")
    build.add_argument(
        "-o", "--output", type=Path,
        help="PDF de saída (padrão: out/<nome do YAML>.pdf)",
    )
    build.add_argument(
        "-t", "--theme", default="classic",
        help="tema embutido ou caminho de um .css (padrão: classic)",
    )
    build.add_argument(
        "--pages", type=_positive_int, default=1,
        help="máximo de páginas; a fonte é ajustada para caber (padrão: 1)",
    )
    build.add_argument(
        "--min-size", type=_positive_float, default=8.0,
        help="fonte mínima em pt (padrão: 8)",
    )
    build.add_argument(
        "--max-size", type=_positive_float, default=12.0,
        help="fonte máxima em pt (padrão: 12)",
    )
    build.add_argument(
        "--font-size", type=_positive_float,
        help="tamanho fixo em pt; desliga o ajuste de página",
    )
    build.add_argument(
        "--preview", action="store_true",
        help="salva também uma imagem PNG de cada página",
    )

    commands.add_parser("themes", help="lista os temas embutidos")
    return parser


def _pages(count: int) -> str:
    return f"{count} {'página' if count == 1 else 'páginas'}"


def _build(args: argparse.Namespace) -> int:
    from resume_builder.pdf import BuildOptions, build_pdf, write_pdf

    resume = load_resume(args.resume)
    options = BuildOptions(
        theme_css=load_theme(args.theme),
        max_pages=args.pages,
        min_size=args.min_size,
        max_size=args.max_size,
        font_size=args.font_size,
    )
    result = build_pdf(resume, options)
    output = write_pdf(result.pdf, args.output or Path("out") / f"{args.resume.stem}.pdf")

    fit = result.fit
    print(f"{output} · {_pages(fit.pages)} · fonte {fit.font_size:g} pt")

    if args.preview:
        from resume_builder.preview import render_previews

        for path in render_previews(result.pdf, output):
            print(f"prévia: {path}")

    if not fit.fits:
        hint = "reduza o conteúdo" if args.font_size else "reduza o conteúdo ou --min-size"
        print(
            f"aviso: não coube em {_pages(args.pages)} com {fit.font_size:g} pt; {hint}",
            file=sys.stderr,
        )
        return EXIT_DOES_NOT_FIT
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "themes":
        print("\n".join(available_themes()))
        return EXIT_OK

    if args.min_size > args.max_size:
        parser.error("--min-size não pode ser maior que --max-size")
    try:
        return _build(args)
    except (ResumeError, ThemeError) as error:
        print(f"erro: {error}", file=sys.stderr)
        return EXIT_INVALID_INPUT
