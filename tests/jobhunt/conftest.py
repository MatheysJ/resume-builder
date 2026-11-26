import shutil
from importlib.resources import files
from pathlib import Path

import pytest

EXAMPLE_RESUME = Path(__file__).resolve().parents[2] / "examples" / "resume.yaml"


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """A data folder with the profile template and the example resume as the master."""
    data = tmp_path / "data"
    data.mkdir()
    template = files("jobhunt").joinpath("templates", "profile.yaml")
    (data / "profile.yaml").write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
    shutil.copy(EXAMPLE_RESUME, data / "master.yaml")
    return data
