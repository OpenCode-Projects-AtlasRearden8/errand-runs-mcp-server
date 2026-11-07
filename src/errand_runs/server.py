"""MCP server exposing the errand runs helper over stdio.

Works with `mcp` 1.x (FastMCP) and 2.x (MCPServer). Run with:

    python -m errand_runs.server

Every tool result is plain, readable text an AI agent can act on.
All data stays on disk at home - no cloud, no accounts, no uploads.
"""

from __future__ import annotations

import os
from pathlib import Path

from .errands import (  # noqa: F401 (compute_run_plan is plan_run renamed)
    BOUGHT,
    NO_STORE,
    ErrandError,
    ErrandItem,
    group_by_store,
    parse_date,
    store_tallies,
)
from .errands import plan_run as compute_run_plan
from .store import ErrandStore

try:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _MCP  # type: ignore

    _MCP_VERSION = "1.x"
except ImportError:  # mcp 2.x
    from mcp.server.mcpserver import MCPServer as _MCP  # type: ignore

    _MCP_VERSION = "2.x"


def _default_path() -> Path:
    raw = os.environ.get("ERRANDS_PATH")
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parent.parent.parent / "data" / "errands.json"


def _money(amount: float) -> str:
    return f"${amount:.2f}"


def _tags_of(item: ErrandItem) -> str:
    return ", ".join(item.stores) if item.stores else NO_STORE


def build_server(store: ErrandStore | None = None):
    """Create the MCP server bound to a store (default path from env)."""
    errand_store = store or ErrandStore(_default_path())
    server = _MCP(
        "errand-runs",
        title="Errand Runs Helper",
        description=(
            "A local errands helper: log items with store tags, get one "
            "low-energy single-run plan (one store plus one backup), close "
            "items after buying, and pull a receipt for the trip. All data "
            "stays on disk at home."
        ),
    )

    def item_line(item: ErrandItem) -> str:
        note = f"  note={item.note}" if item.note else ""
        return (
            f"{item.id}  {item.name} x{item.quantity}  "
            f"stores={_tags_of(item)}{note}"
        )

    @server.tool()
    def log_item(
        item: str,
        stores: list[str] | None = None,
        quantity: int = 1,
        note: str = "",
    ) -> str:
        """Log one errand item and tag it with the store(s) that can sell it
        (for example ["Canal Market", "Maple Drugstore"]). Quantity defaults
        to 1. Leaving stores empty still logs the item, but it cannot be
        planned into a run until it has a store tag."""
        try:
            added = errand_store.add_item(item, stores, quantity, note)
        except ErrandError as exc:
            return f"Could not log the item: {exc}"
        return (
            f"Logged {added.id}: {added.name} x{added.quantity}, "
            f"tagged for {_tags_of(added)}. It is on the open list."
        )

    @server.tool()
    def tally() -> str:
        """Show the open list grouped by store tag, with a count per store
        (busiest first). This is the quick 'how long is each store's list'
        view before planning a run."""
        open_items = errand_store.open_items()
        bought_count = len(errand_store.all_items()) - len(open_items)
        if not open_items:
            extra = f" ({bought_count} already bought)" if bought_count else ""
            return (
                "Nothing left to buy"
                + extra
                + " - use `log_item` to add the next thing."
            )
        grouped = group_by_store(open_items)
        lines = ["Open list, grouped by store:"]
        for store_name, items in grouped.items():
            lines.append(f"  {store_name} ({len(items)} items)")
            for item in items:
                lines.append(f"    - {item_line(item)}")
        counts = ", ".join(
            f"{name} {count}" for name, count in store_tallies(open_items)
        )
        lines.append(f"Counts per store: {counts}")
        return "\n".join(lines)

    @server.tool()
    def plan_run(max_stops: int = 2) -> str:
        """Plan one low-energy errand run: a single trip covering at most
        `max_stops` stores (default 2 - the one-plus-one mode: one main stop,
        plus one if it clearly helps). The stop combo is picked to chip away
        as much of the open list as possible, so whatever is left over stays
        short."""
        try:
            legs, leftover = compute_run_plan(errand_store.open_items(), max_stops)
        except ErrandError as exc:
            return f"Could not plan the run: {exc}"
        if not legs:
            if any(i.stores for i in errand_store.open_items()):
                return (
                    "Could not plan a run: the store tags on file look "
                    "empty. Double-check them with `tally`."
                )
            return "No open items on file yet - log one with `log_item` first."
        covered = sum(len(items) for _, items in legs)
        open_count = len(errand_store.open_items())
        lines = [
            f"One low-energy run (up to {max_stops} stops) covers "
            f"{covered} of {open_count} open items.",
            "Suggested order - busiest stop first:",
        ]
        for index, (store_name, items) in enumerate(legs, start=1):
            lines.append(f"  Leg {index} - {store_name} ({len(items)} items)")
            for item in items:
                lines.append(f"    - {item.name} x{item.quantity}  [{item.id}]")
        if leftover:
            parts = []
            if any(i.stores for i in leftover):
                parts.append("no stop combo within the limit covers them")
            if any(not i.stores for i in leftover):
                parts.append("they still need a store tag")
            names = ", ".join(f"{i.name} x{i.quantity}" for i in leftover)
            lines.append(f"Left off this run ({names}) - {'; '.join(parts)}.")
        lines.append(
            "After the run, close each item with `mark_bought`, then pull "
            "the day's summary with `receipt`."
        )
        return "\n".join(lines)

    @server.tool()
    def mark_bought(
        item: str,
        price: float | None = None,
        store: str = "",
        bought_on: str = "",
    ) -> str:
        """Close an item as bought: reference it by id (I-3) or name
        ('oat milk'). Price is what you paid, if you want it on the receipt.
        For items tagged with several stores, say which store it came from
        using `store`. Use bought_on (YYYY-MM-DD) only when closing for a
        past day; the default is today."""
        try:
            found = errand_store.find_item(item)
            closed = errand_store.mark_bought(found, bought_on, store, price)
        except ErrandError as exc:
            return f"Could not close the item: {exc}"
        paid = (
            f", paid {_money(closed.price)}" if closed.price is not None else ""
        )
        return (
            f"Closed {closed.id} ({closed.name}) - bought at "
            f"{closed.bought_store or 'an untold store'} on "
            f"{closed.bought_on.isoformat()}{paid}."
        )

    @server.tool()
    def receipt(bought_on: str = "") -> str:
        """After-the-fact closure query: the receipt for one trip day
        (YYYY-MM-DD, default today). Lists what was bought, per-store
        subtotals, the total paid, and where the open list stands."""
        try:
            day = parse_date(bought_on) if bought_on else errand_store.today()
        except ErrandError as exc:
            return f"Could not read the receipt date: {exc}"
        bought = errand_store.bought_on(day)
        if not bought:
            return (
                f"No items bought on {day.isoformat()} yet. Close the run "
                "with `mark_bought` and try again."
            )
        lines = [f"Receipt for {day.isoformat()}: {len(bought)} item(s) bought."]
        by_store: dict[str, list[ErrandItem]] = {}
        for item in bought:
            price_text = (
                _money(item.price) if item.price is not None else "no price recorded"
            )
            lines.append(
                f"  {item.id}  {item.name} x{item.quantity}  "
                f"{item.bought_store or NO_STORE}  {price_text}"
            )
            by_store.setdefault(item.bought_store or NO_STORE, []).append(item)
        for store_name in sorted(by_store, key=str.casefold):
            rows = by_store[store_name]
            priced = [i for i in rows if i.price is not None]
            subtotal = sum(i.price for i in priced)
            note = "" if len(priced) == len(rows) else " (some prices unrecorded)"
            lines.append(f"  Subtotal - {store_name}: {_money(subtotal)}{note}")
        paid = [i for i in bought if i.price is not None]
        unpriced_count = len(bought) - len(paid)
        grand = sum(i.price for i in paid)  # type: ignore[arg-type]
        tail = f"Total paid: {_money(grand)}"
        if unpriced_count:
            tail += f" ({unpriced_count} item(s) with no price recorded)"
        still_open = errand_store.open_items()
        if still_open:
            tallies = ", ".join(f"{n} {c}" for n, c in store_tallies(still_open))
            lines.append(f"Still open: {len(still_open)} item(s) - {tallies}.")
        else:
            lines.append("That empties the open list. Bag done.")
        lines.append(tail + ".")
        return "\n".join(lines)

    @server.tool()
    def list_items(status: str = "open") -> str:
        """List logged items: 'open' (default) for things still to buy,
        'bought' for closed ones, 'all' for both. Handy for double-checking
        the log before planning or closing a run."""
        want = status.strip().lower()
        if want not in {"open", "bought", "all"}:
            return "status should be 'open', 'bought', or 'all'."
        filtered = [
            i for i in errand_store.all_items() if want == "all" or i.status == want
        ]
        if not filtered:
            return f"No {want} items on file yet."
        lines = [f"{len(filtered)} {want or 'logged'} item(s):"]
        for item in filtered:
            extra = ""
            if item.status == BOUGHT:
                day = item.bought_on.isoformat() if item.bought_on else "?"
                paid = (
                    f" for {_money(item.price)}" if item.price is not None else ""
                )
                extra = (
                    f"  bought {day} at "
                    f"{item.bought_store or 'an untold store'}{paid}"
                )
            lines.append(f"  {item_line(item)}{extra}")
        return "\n".join(lines)

    return server


def main() -> None:
    import sys

    server = build_server()
    print(
        f"errand-runs MCP server ({_MCP_VERSION}) starting on stdio...",
        file=sys.stderr,
    )
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
