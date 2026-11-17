from __future__ import annotations

import re
from pathlib import Path

import pypdfium2 as pdfium

DEFAULT_SCALE = 2.0


def render_previews(pdf: bytes, output: str | Path, scale: float = DEFAULT_SCALE) -> list[Path]:
    output = Path(output)
    previous = re.compile(rf"{re.escape(output.stem)}(-\d+)?\.png")
    for stale in output.parent.glob(f"{output.stem}*.png"):
        if previous.fullmatch(stale.name):
            stale.unlink()

    document = pdfium.PdfDocument(pdf)
    try:
        total = len(document)
        paths = []
        for index in range(total):
            suffix = "" if total == 1 else f"-{index + 1}"
            path = output.with_name(f"{output.stem}{suffix}.png")
            document[index].render(scale=scale).to_pil().save(path)
            paths.append(path)
        return paths
    finally:
        document.close()
