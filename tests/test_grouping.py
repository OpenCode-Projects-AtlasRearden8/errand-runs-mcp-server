"""Tests for grouping items by store tag and the per-store tally."""

from __future__ import annotations

from errand_runs.errands import NO_STORE, group_by_store, store_tallies


class TestGroupByStore:
    def test_items_go_under_every_tag_they_carry(self, busy_store) -> None:
        grouped = group_by_store(busy_store.open_items())
        canal = [item.name for item in grouped["Canal Market"]]
        maple = [item.name for item in grouped["Maple Drugstore"]]
        assert "oat milk" in canal and "oat milk" in maple  # tagged with both
        assert "bread" in canal and "apples" in canal
        assert "stamps" not in maple  # bought, so off the open list

    def test_untagged_items_land_in_the_no_store_bucket(self, busy_store) -> None:
        grouped = group_by_store(busy_store.open_items())
        assert [i.name for i in grouped[NO_STORE]] == ["mystery item"]

    def test_store_tag_dedupe_is_case_insensitive(self, fresh_store) -> None:
        item = fresh_store.add_item(
            "oat milk", ["Canal Market", "canal market", "CANAL MARKET"]
        )
        assert item.stores == ["Canal Market"]

    def test_empty_store_tags_reported_clearly(self, fresh_store) -> None:
        try:
            fresh_store.add_item("oat milk", ["   "])
        except Exception as exc:
            assert "short names" in str(exc)
        else:
            raise AssertionError("a blank store tag should be refused")

    def test_groups_are_sorted_alphabetically(self, busy_store) -> None:
        grouped = group_by_store(busy_store.open_items())
        names = list(grouped)
        assert names == sorted(names, key=str.casefold)


class TestStoreTallies:
    def test_counts_only_open_items(self, busy_store) -> None:
        tallies = dict(store_tallies(busy_store.open_items()))
        # stamps is bought, so Maple Drugstore only counts 2 open items here
        assert tallies["Maple Drugstore"] == 2

    def test_busiest_store_first_then_alphabetical(self, busy_store) -> None:
        tallies = store_tallies(busy_store.open_items())
        order = [name for name, _ in tallies]
        assert order == [
            "BigBox Mart",
            "Canal Market",
            "Maple Drugstore",
            NO_STORE,
        ]
        assert tallies[0][1] == 4  # BigBox Mart: chalk, rubber bands, batteries, handsaw

    def test_tally_skips_bought_items_everywhere(self, fresh_store) -> None:
        fresh_store.add_item("only thing", ["Canal Market"])
        item = fresh_store.find_item("only thing")
        fresh_store.mark_bought(item, price=9.99)
        assert store_tallies(fresh_store.open_items()) == []
