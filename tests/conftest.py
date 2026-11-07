"""Shared fixtures: a temp store and a frozen 'today' so tests are reproducible.

All fixture data is synthetic - no personal data, ever.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from errand_runs.store import ErrandStore

TODAY = date(2026, 11, 7)


@pytest.fixture
def fresh_store(tmp_path: Path) -> ErrandStore:
    store = ErrandStore(tmp_path / "errands.json")
    store._today = lambda: TODAY
    return store


@pytest.fixture
def busy_store(tmp_path: Path) -> ErrandStore:
    """A store spread across store tags, with one item already bought."""
    store = ErrandStore(tmp_path / "errands.json")
    store._today = lambda: TODAY
    store.add_item("oat milk", ["Canal Market", "Maple Drugstore"])
    store.add_item("bread", ["Canal Market"], quantity=2)
    store.add_item("apples", ["Canal Market"], quantity=3)
    store.add_item("stamps", ["Maple Drugstore"])
    store.add_item("chalk", ["BigBox Mart"])
    store.add_item("rubber bands", ["Maple Drugstore", "BigBox Mart"])
    store.add_item("batteries", ["BigBox Mart"])
    store.add_item("handsaw", ["Canal Market", "BigBox Mart"])
    store.add_item("mystery item")  # no store tag yet
    store.mark_bought(
        store.find_item("stamps"), on="2026-11-07", store="Maple Drugstore",
        price=11.90,
    )
    return store
