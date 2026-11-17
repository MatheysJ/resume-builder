from __future__ import annotations

import io
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from resume_builder import PDF_CREATOR, PDF_PRODUCER
from resume_builder.fit import FitResult, fit_font_size
from resume_builder.model import Meta, Resume
from resume_builder.render import render_html


@dataclass(frozen=True)
class BuildOptions:
    theme_css: str
    max_pages: int = 1
    min_size: float = 8.0
    max_size: float = 12.0
    font_size: float | None = None


@dataclass(frozen=True)
class BuildResult:
    pdf: bytes
    fit: FitResult


def build_pdf(resume: Resume, options: BuildOptions) -> BuildResult:
    # Lazy import: WeasyPrint fails to load without Pango, and the rest of the package must not.
    from weasyprint import HTML

    @lru_cache(maxsize=None)
    def render(font_size: float):
        html = render_html(resume, options.theme_css, font_size)
        return HTML(string=html).render()

    def count_pages(font_size: float) -> int:
        return len(render(font_size).pages)

    if options.font_size is not None:
        pages = count_pages(options.font_size)
        fit = FitResult(options.font_size, pages, pages <= options.max_pages, 1)
    else:
        fit = fit_font_size(
            count_pages,
            max_pages=options.max_pages,
            min_size=options.min_size,
            max_size=options.max_size,
        )

    pdf = render(fit.font_size).write_pdf()
    return BuildResult(pdf=apply_metadata(pdf, resume.meta), fit=fit)


def apply_metadata(pdf: bytes, meta: Meta) -> bytes:
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(pdf)))
    info = {
        "/Title": meta.title,
        "/Author": meta.author,
        "/Creator": PDF_CREATOR,
        "/Producer": PDF_PRODUCER,
    }
    if meta.subject:
        info["/Subject"] = meta.subject
    if meta.keywords:
        info["/Keywords"] = ", ".join(meta.keywords)
    writer.add_metadata(info)

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def write_pdf(pdf: bytes, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pdf)
    return path
