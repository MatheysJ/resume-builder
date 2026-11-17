import io
from dataclasses import replace

import pytest
from pypdf import PdfReader

try:
    import weasyprint  # noqa: F401
except (ImportError, OSError):  # missing Pango raises OSError
    pytest.skip("WeasyPrint indisponível neste ambiente", allow_module_level=True)

from resume_builder.cli import main
from resume_builder.model import Entry
from resume_builder.pdf import BuildOptions, build_pdf
from resume_builder.theming import available_themes, load_theme


def read(pdf: bytes) -> PdfReader:
    return PdfReader(io.BytesIO(pdf))


def link_targets(reader: PdfReader) -> set[str]:
    targets = set()
    for page in reader.pages:
        for annotation in page.get("/Annots") or []:
            action = annotation.get_object().get("/A")
            if action and "/URI" in action:
                targets.add(action["/URI"])
    return targets


@pytest.mark.parametrize("theme", available_themes())
def test_fits_in_one_page_with_extractable_text(example, theme):
    result = build_pdf(example, BuildOptions(theme_css=load_theme(theme)))
    reader = read(result.pdf)

    assert result.fit.fits
    assert len(reader.pages) == 1
    # CSS text-transform uppercases the extracted headings.
    text = reader.pages[0].extract_text().casefold()
    for expected in ("Ana Souza", "Experiência", "Spring Boot", "@MatheysJ/resume-builder"):
        assert expected.casefold() in text


def test_links_are_clickable(example):
    reader = read(build_pdf(example, BuildOptions(theme_css=load_theme("classic"))).pdf)

    assert {
        "mailto:ana.souza@example.com",
        "tel:+5511900000000",
        "https://www.linkedin.com/in/ana-souza-exemplo",
        "https://github.com/ana-souza-exemplo/conciliador",
        "https://github.com/MatheysJ/resume-builder",
    } <= link_targets(reader)


def test_metadata_is_controlled(example):
    reader = read(build_pdf(example, BuildOptions(theme_css=load_theme("classic"))).pdf)
    meta = reader.metadata

    assert meta.title == "Currículo · Ana Souza"
    assert meta.author == "Ana Souza"
    assert meta.creator == "@MatheysJ/resume-builder (https://github.com/MatheysJ/resume-builder)"
    assert meta.producer.startswith("@MatheysJ/resume-builder ")
    assert "pypdf" not in str(dict(meta)).lower()


def test_long_content_shrinks_the_font(example):
    experience = example.sections[0]
    longer = replace(
        experience,
        entries=experience.entries + tuple(
            Entry(title=f"Cargo {i}", bullets=("Texto longo de exemplo. " * 6,) * 3)
            for i in range(3)
        ),
    )
    longer_resume = replace(example, sections=(longer, *example.sections[1:]))
    options = BuildOptions(theme_css=load_theme("classic"))

    short = build_pdf(example, options).fit
    long = build_pdf(longer_resume, options).fit

    assert long.font_size < short.font_size
    assert long.pages == 1


def test_cli_builds_pdf_and_preview(example_path, tmp_path, capsys):
    output = tmp_path / "cv.pdf"

    code = main(["build", str(example_path), "-o", str(output), "--theme", "sidebar", "--preview"])

    assert code == 0
    assert output.is_file()
    assert (tmp_path / "cv.png").is_file()
    assert "1 página" in capsys.readouterr().out
