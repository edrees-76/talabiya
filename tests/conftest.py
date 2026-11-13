from __future__ import annotations

import pytest

from talabiya.core.db import connect
from talabiya.core.repo import Repo
from talabiya.core.seed import ITEMS, UNITS


@pytest.fixture
def repo(tmp_path):
    conn = connect(tmp_path / "t.db")
    r = Repo(conn)
    r.seed_catalog(UNITS, ITEMS)
    yield r
    conn.close()
