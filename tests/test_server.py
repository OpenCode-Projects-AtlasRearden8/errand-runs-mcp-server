"""End-to-end tests for the MCP server: tool listing, calls, readable text."""

from __future__ import annotations

import asyncio
from typing import Any

from errand_runs.server import build_server
from errand_runs.store import ErrandStore


def run(coro: Any) -> Any:
    return asyncio.run(coro)


def tool_text(result: Any) -> str:
    assert result.is_error is False, result
    return result.content[0].text  # type: ignore[union-attr, index]


class TestToolListing:
    def test_list_tools(self, fresh_store: ErrandStore) -> None:
        names = {t.name for t in run(build_server(fresh_store).list_tools())}
        assert {
            "log_item",
            "tally",
            "plan_run",
            "mark_bought",
            "receipt",
            "list_items",
        } == names


class TestLogItemTool:
    def test_log_and_read_back(self, fresh_store: ErrandStore) -> None:
        text = tool_text(run(build_server(fresh_store).call_tool(
            "log_item",
            {"item": "oat milk", "stores": ["Canal Market", "Maple Drugstore"]},
        )))
        assert "Logged I-1: oat milk x1" in text
        assert "Canal Market, Maple Drugstore" in text

    def test_logged_item_is_not_tagged_warning_free(self, fresh_store) -> None:
        text = tool_text(run(build_server(fresh_store).call_tool(
            "log_item", {"item": "mystery item"},
        )))
        assert "(no store tagged)" in text

    def test_bad_quantity_reports_gracefully(self, fresh_store: ErrandStore) -> None:
        text = tool_text(run(build_server(fresh_store).call_tool(
            "log_item", {"item": "bread", "quantity": 0},
        )))
        assert "Could not log the item" in text


class TestTallyTool:
    def test_empty_list_message(self, fresh_store: ErrandStore) -> None:
        text = tool_text(run(build_server(fresh_store).call_tool("tally", {})))
        assert "Nothing left to buy" in text

    def test_grouping_and_counts(self, busy_store: ErrandStore) -> None:
        text = tool_text(run(build_server(busy_store).call_tool("tally", {})))
        assert "Canal Market (4 items)" in text
        assert "BigBox Mart (4 items)" in text
        assert "Maple Drugstore (2 items)" in text
        assert "(no store tagged) (1 items)" in text
        assert "Counts per store:" in text
        assert "stamps" not in text  # bought items stay off the open list


class TestPlanRunTool:
    def test_one_plus_one_plan(self, busy_store: ErrandStore) -> None:
        text = tool_text(run(build_server(busy_store).call_tool("plan_run", {})))
        assert "up to 2 stops" in text
        assert "Leg 1 - " in text and "Leg 2 - " in text
        assert "Left off this run" in text
        assert "still need a store tag" in text
        assert "mark_bought" in text and "receipt" in text

    def test_single_stop_plan(self, busy_store: ErrandStore) -> None:
        text = tool_text(run(build_server(busy_store).call_tool(
            "plan_run", {"max_stops": 1},
        )))
        assert "up to 1 stops" in text
        assert "BigBox Mart" in text
        assert "Left off this run" in text

    def test_plan_without_items(self, fresh_store: ErrandStore) -> None:
        text = tool_text(run(build_server(fresh_store).call_tool("plan_run", {})))
        assert "No open items on file yet" in text

    def test_over_the_cap_reports_gracefully(self, busy_store: ErrandStore) -> None:
        text = tool_text(run(build_server(busy_store).call_tool(
            "plan_run", {"max_stops": 9},
        )))
        assert "Could not plan the run" in text


class TestMarkBoughtTool:
    def test_close_and_confirm(self, fresh_store: ErrandStore) -> None:
        server = build_server(fresh_store)
        tool_text(run(server.call_tool(
            "log_item", {"item": "bread", "stores": ["Canal Market"]},
        )))
        text = tool_text(run(server.call_tool(
            "mark_bought", {"item": "bread", "price": 3.75},
        )))
        assert "Closed I-1 (bread)" in text
        assert "Canal Market" in text and "2026-11-07" in text and "$3.75" in text

    def test_multi_store_needs_the_stop_named(self, fresh_store: ErrandStore) -> None:
        server = build_server(fresh_store)
        tool_text(run(server.call_tool(
            "log_item",
            {"item": "oat milk", "stores": ["Canal Market", "Maple Drugstore"]},
        )))
        text = tool_text(run(server.call_tool(
            "mark_bought", {"item": "oat milk", "price": 4.2},
        )))
        assert "which store" in text
        text = tool_text(run(server.call_tool(
            "mark_bought", {"item": "oat milk", "price": 4.2, "store": "Canal Market"},
        )))
        assert "Closed I-1 (oat milk)" in text

    def test_double_close_is_friendly(self, fresh_store: ErrandStore) -> None:
        server = build_server(fresh_store)
        tool_text(run(server.call_tool(
            "log_item", {"item": "bread", "stores": ["Canal Market"]},
        )))
        tool_text(run(server.call_tool("mark_bought", {"item": "bread"})))
        text = tool_text(run(server.call_tool("mark_bought", {"item": "bread"})))
        assert "already bought" in text

    def test_unknown_item_is_friendly(self, fresh_store: ErrandStore) -> None:
        text = tool_text(run(build_server(fresh_store).call_tool(
            "mark_bought", {"item": "trampoline"},
        )))
        assert "Could not close the item" in text


class TestReceiptTool:
    def test_receipt_after_the_run(self, busy_store: ErrandStore) -> None:
        server = build_server(busy_store)
        tool_text(run(server.call_tool(
            "mark_bought", {"item": "bread", "price": 2.4},
        )))
        tool_text(run(server.call_tool(
            "mark_bought", {"item": "oat milk", "price": 4.25,
                            "store": "Maple Drugstore"},
        )))
        text = tool_text(run(server.call_tool("receipt", {})))
        assert "Receipt for 2026-11-07: 3 item(s) bought" in text
        assert "I-2  bread x2  Canal Market  $2.40" in text
        assert "I-1  oat milk x1  Maple Drugstore  $4.25" in text
        assert "Subtotal - Canal Market: $2.40" in text
        assert "Subtotal - Maple Drugstore: $16.15" in text  # 11.90 fixture + 4.25
        assert "Total paid: $18.55" in text
        assert "Still open:" in text

    def test_receipt_with_unpriced_items(self, fresh_store: ErrandStore) -> None:
        server = build_server(fresh_store)
        tool_text(run(server.call_tool(
            "log_item", {"item": "bread", "stores": ["Canal Market"]},
        )))
        tool_text(run(server.call_tool("mark_bought", {"item": "bread"})))
        text = tool_text(run(server.call_tool("receipt", {})))
        assert "no price recorded" in text
        assert "Total paid: $0.00 (1 item(s) with no price recorded)" in text
        assert "empties the open list" in text

    def test_receipt_before_anything_was_bought(self, busy_store) -> None:
        server = build_server(busy_store)
        text = tool_text(run(server.call_tool(
            "receipt", {"bought_on": "2026-11-06"},
        )))
        assert "No items bought on 2026-11-06" in text

    def test_bad_date_reports_gracefully(self, busy_store) -> None:
        text = tool_text(run(build_server(busy_store).call_tool(
            "receipt", {"bought_on": "Nov 5"},
        )))
        assert "Could not read the receipt date" in text


class TestListItemsTool:
    def test_open_by_default(self, busy_store: ErrandStore) -> None:
        text = tool_text(run(build_server(busy_store).call_tool("list_items", {})))
        assert "8 open item(s)" in text
        assert "bought 2026-11-07" not in text

    def test_bought_only(self, busy_store: ErrandStore) -> None:
        text = tool_text(run(build_server(busy_store).call_tool(
            "list_items", {"status": "bought"},
        )))
        assert "stamps" in text and "$11.90" in text

    def test_bad_status_is_friendly(self, busy_store: ErrandStore) -> None:
        text = tool_text(run(build_server(busy_store).call_tool(
            "list_items", {"status": "later"},
        )))
        assert "status should be" in text
