"""Tests for the store: logging, finding, closing, receipts, persistence."""

from __future__ import annotations

import json
from datetime import date

import pytest

from errand_runs.errands import ErrandError
from errand_runs.store import ErrandStore


class TestLogItem:
    def test_ids_increase_and_names_are_trimmed(self, fresh_store) -> None:
        first = fresh_store.add_item("  oat   milk ")
        assert first.id == "I-1" and first.name == "oat milk"
        assert fresh_store.add_item("bread").id == "I-2"

    def test_blank_names_are_refused(self, fresh_store) -> None:
        with pytest.raises(ErrandError):
            fresh_store.add_item("   ")

    def test_quantity_must_be_positive(self, fresh_store) -> None:
        with pytest.raises(ErrandError):
            fresh_store.add_item("bread", quantity=0)

    def test_logged_date_is_the_frozen_today(self, fresh_store) -> None:
        assert fresh_store.add_item("bread").logged == date(2026, 11, 7)


class TestFindItem:
    def test_find_by_id_case_insensitive(self, busy_store) -> None:
        assert busy_store.find_item("i-2").name == "bread"

    def test_find_by_name_ignores_case(self, busy_store) -> None:
        assert busy_store.find_item("OAT MILK").id == "I-1"

    def test_unique_substring_match_works(self, busy_store) -> None:
        assert busy_store.find_item("hand").name == "handsaw"

    def test_ambiguous_match_points_back_to_ids(self, busy_store) -> None:
        with pytest.raises(ErrandError) as exc_info:
            busy_store.find_item("s")  # matches several item names
        assert "Use an id" in str(exc_info.value)

    def test_unknown_item_is_friendly(self, busy_store) -> None:
        with pytest.raises(ErrandError):
            busy_store.find_item("trampoline")


class TestMarkBought:
    def test_close_defaults_to_today_and_sole_store(self, fresh_store) -> None:
        fresh_store.add_item("bread", ["Canal Market"])
        bought = fresh_store.mark_bought(fresh_store.find_item("bread"), price=3.75)
        assert bought.status == "bought"
        assert bought.bought_on == date(2026, 11, 7)
        assert bought.bought_store == "Canal Market"
        assert bought.price == 3.75

    def test_multi_store_item_needs_the_store_named(self, fresh_store) -> None:
        fresh_store.add_item("oat milk", ["Canal Market", "Maple Drugstore"])
        with pytest.raises(ErrandError) as exc_info:
            fresh_store.mark_bought(fresh_store.find_item("oat milk"), price=4.2)
        assert "which store" in str(exc_info.value)
        bought = fresh_store.mark_bought(
            fresh_store.find_item("oat milk"), store="Canal Market", price=4.2
        )
        assert bought.bought_store == "Canal Market"

    def test_double_close_is_refused(self, fresh_store) -> None:
        fresh_store.add_item("bread", ["Canal Market"])
        item = fresh_store.find_item("bread")
        fresh_store.mark_bought(item)
        with pytest.raises(ErrandError) as exc_info:
            fresh_store.mark_bought(item)
        assert "already bought" in str(exc_info.value)

    def test_negative_price_is_refused(self, fresh_store) -> None:
        fresh_store.add_item("bread", ["Canal Market"])
        item = fresh_store.find_item("bread")
        with pytest.raises(ErrandError):
            fresh_store.mark_bought(item, price=-1)


class TestReceipts:
    def test_bought_on_filters_by_day(self, busy_store) -> None:
        # stamps was bought today in the fixture
        today_items = busy_store.bought_on(date(2026, 11, 7))
        assert [i.name for i in today_items] == ["stamps"]
        assert busy_store.bought_on(date(2026, 11, 6)) == []

    def test_open_items_exclude_closed_ones(self, busy_store) -> None:
        fresh_store_cone = busy_store
        closed = [i.name for i in fresh_store_cone.bought_on(date(2026, 11, 7))]
        assert closed == ["stamps"]
        open_names = [i.name for i in busy_store.open_items()]
        assert "stamps" not in open_names


class TestPersistence:
    def test_data_survives_a_reload(self, fresh_store, tmp_path) -> None:
        fresh_store.add_item("oat milk", ["Canal Market"], quantity=2, note="barista blend")
        fresh_store.mark_bought(fresh_store.find_item("oat milk"), store=None, price=4.5)
        reloaded = ErrandStore(tmp_path / "errands.json")
        reloaded._today = lambda: date(2026, 11, 7)
        item = reloaded.find_item("oat milk")
        assert item.quantity == 2 and item.note == "barista blend"
        assert item.bought_store == "Canal Market" and item.price == 4.5
        assert reloaded.all_items()[0].logged == date(2026, 11, 7)

    def test_next_item_id_survives_a_reload(self, fresh_store, tmp_path) -> None:
        fresh_store.add_item("bread", ["Canal Market"])
        reloaded = ErrandStore(tmp_path / "errands.json")
        assert reloaded.add_item("apples").id == "I-2"

    def test_file_is_pretty_json(self, fresh_store, tmp_path) -> None:
        fresh_store.add_item("bread", ["Canal Market"])
        raw = json.loads((tmp_path / "errands.json").read_text(encoding="utf-8"))
        assert raw["items"][0]["name"] == "bread"
        assert "  " in (tmp_path / "errands.json").read_text(encoding="utf-8")

    def test_corrupt_file_raises_a_readable_error(self, tmp_path) -> None:
        path = tmp_path / "broken.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(ErrandError) as exc_info:
            ErrandStore(path)
        assert "Could not read" in str(exc_info.value)

    def test_missing_file_starts_empty(self, tmp_path) -> None:
        store = ErrandStore(tmp_path / "brand" / "new.json")
        assert store.all_items() == []
