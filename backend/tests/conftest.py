import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest  # noqa: E402

from app.config import load_config  # noqa: E402
from app.store import Store  # noqa: E402


@pytest.fixture()
def cfg():
    return load_config()


@pytest.fixture()
def store(tmp_path):
    s = Store(tmp_path / "test.db")
    yield s
    s.close()
