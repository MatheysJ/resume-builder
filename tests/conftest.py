from pathlib import Path

import pytest

from resume_builder.model import Resume, load_resume

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "resume.yaml"


@pytest.fixture
def example_path() -> Path:
    return EXAMPLE


@pytest.fixture
def example() -> Resume:
    return load_resume(EXAMPLE)
