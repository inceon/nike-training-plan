from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from parser import parse_training_pdf


PDF_PATH = REPO_ROOT / "docs" / "nike-run-club-marathon-ru_RU.pdf"


@lru_cache(maxsize=1)
def _parsed_document():
    return parse_training_pdf(PDF_PATH)


@pytest.fixture(scope="session")
def document():
    return _parsed_document()
