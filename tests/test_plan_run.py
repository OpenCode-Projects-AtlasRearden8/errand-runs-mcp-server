"""Tests for the one-plus-one run planner."""

from __future__ import annotations

from errand_runs.errands import plan_run


class TestPlanRun:
    def test_two_stops_cover_everything_tagged(self, busy_store) -> None:
        legs, leftover = plan_run(busy_store.open_items(), max_stops=2)
        covered = {item.id for _, items in legs for item in items}
        tagged = [i for i in busy_store.open_items() if i.stores]
        assert covered == {item.id for item in tagged}
        # the only leftovers are items with no store tag
        assert all(not item.stores for item in leftover)
        # both legs carry 4 items; ties go alphabetical (BigBox Mart first)
        assert [name for name, _ in legs] == ["BigBox Mart", "Canal Market"]

    def test_legs_ordered_busiest_first(self, busy_store) -> None:
        legs, _ = plan_run(busy_store.open_items(), max_stops=2)
        sizes = [len(items) for _, items in legs]
        assert sizes == sorted(sizes, reverse=True)
        assert sizes[0] == 4  # Canal Market or BigBox Mart, both carry 4

    def test_one_store_mode_picks_the_single_best_stop(self, busy_store) -> None:
        legs, leftover = plan_run(busy_store.open_items(), max_stops=1)
        assert [name for name, _ in legs] == ["BigBox Mart"]
        covered = {item.id for _, items in legs for item in items}
        assert covered == {
            item.id
            for item in busy_store.open_items()
            if "BigBox Mart" in item.stores
        }
        # untagged items ride along as leftovers
        assert [i.name for i in leftover if not i.stores] == ["mystery item"]

    def test_tie_break_is_alphabetical(self, fresh_store) -> None:
        # Canal Market and Maple Drugstore each cover exactly 1 item;
        # alphabetical order must win the tie.
        fresh_store.add_item("maple syrup", ["Maple Drugstore"])
        fresh_store.add_item("bread", ["Canal Market"])
        legs, _ = plan_run(fresh_store.open_items(), max_stops=1)
        assert [name for name, _ in legs] == ["Canal Market"]

    def test_pair_beats_single_stop(self, fresh_store) -> None:
        fresh_store.add_item("oat milk", ["Canal Market", "Maple Drugstore"])
        fresh_store.add_item("chalk", ["BigBox Mart"])
        legs, leftover = plan_run(fresh_store.open_items(), max_stops=2)
        assert len(legs) == 2
        assert leftover == []

    def test_empty_store_brings_back_an_empty_plan(self, fresh_store) -> None:
        legs, leftover = plan_run([])
        assert legs == [] and leftover == []

    def test_all_untagged_returns_nothing_runnable(self, fresh_store) -> None:
        fresh_store.add_item("mystery item")
        legs, leftover = plan_run(fresh_store.open_items())
        assert legs == []
        assert [i.name for i in leftover] == ["mystery item"]

    def test_max_stops_is_capped(self, busy_store) -> None:
        try:
            plan_run(busy_store.open_items(), max_stops=9)
        except Exception as exc:
            assert "capped at 4" in str(exc)
        else:
            raise AssertionError("max_stops should be capped")

    def test_three_stops_stay_a_single_run(self, fresh_store) -> None:
        fresh_store.add_item("bread", ["Canal Market"])
        fresh_store.add_item("stamps", ["Maple Drugstore"])
        fresh_store.add_item("chalk", ["BigBox Mart"])
        legs, leftover = plan_run(fresh_store.open_items(), max_stops=3)
        assert len(legs) == 3
        assert leftover == []
