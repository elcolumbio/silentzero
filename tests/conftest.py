import json
from pathlib import Path

import pytest

CASES = Path(__file__).parent / "cases"


@pytest.fixture
def capture():
    """Load one of the responses captured from a live ATS, verbatim."""
    def _load(name: str):
        return json.loads((CASES / f"{name}.json").read_text())
    return _load
