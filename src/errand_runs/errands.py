"""Pure domain logic for errands: items, store tags, grouping, and runs.

Everything here is plain data plus simple math, so it is easy to test with a
frozen "today". Persistence lives in store.py, MCP wiring in server.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from itertools import combinations

OPEN = "open"
BOUGHT = "bought"
NO_STORE = "(no store tagged)"
MAX_STOPS_CAP = 4


class ErrandError(Exception):
    """Friendly, actionable error for an errand problem."""


@dataclass
class ErrandItem:
    id: str
    name: str
    stores: list[str]
    quantity: int
    note: str
    status: str
    logged: date
    bought_on: date | None = None
    bought_store: str | None = None
    price: float | None = None


def parse_date(raw: str) -> date:
    """Parse an ISO date (YYYY-MM-DD) and raise a readable error otherwise."""
    if not isinstance(raw, str):
        raise ErrandError("Dates should be text in YYYY-MM-DD form, like 2026-11-15.")
    try:
        return date.fromisoformat(raw.strip())
    except ValueError:
        raise ErrandError(
            f"Could not read the date {raw!r}. Use YYYY-MM-DD, like 2026-11-15."
        ) from None


def parse_positive_int(raw: int, what: str, default: int) -> int:
    """Coerce a quantity/count, keeping it a positive whole number."""
    if raw is None:
        return default
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ErrandError(f"{what} should be a whole number, got {raw!r}.")
    if raw < 1:
        raise ErrandError(f"{what} should be at least 1, got {raw}.")
    return raw


def clean_name(raw: str) -> str:
    """Trim an item name and insist it is not empty."""
    if not isinstance(raw, str) or not raw.strip():
        raise ErrandError("Give the item a short name, like 'oat milk'.")
    return " ".join(raw.strip().split())


def normalize_name(raw: str) -> str:
    """Lowercase, whitespace-collapsed form used for matching."""
    return clean_name(raw).lower()


def clean_stores(raw: list[str] | None) -> list[str]:
    """Validate store tags: drop blanks, dedupe case-insensitively."""
    if raw is None or raw == "":
        return []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, (list, tuple)):
        raise ErrandError(
            "Store tags should be a list of short names, like "
            "['Canal Market', 'Maple Drugstore']."
        )
    cleaned: list[str] = []
    seen: set[str] = set()
    for tag in raw:
        if not isinstance(tag, str) or not tag.strip():
            raise ErrandError("Store tags should be short names, not blanks.")
        tag = " ".join(tag.strip().split())
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(tag)
    return cleaned


def parse_price(raw: float | None) -> float | None:
    """Validate an optional price: non-negative, at most pennies are kept."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ErrandError("Price should be a number, like 3.50 (leave blank if unknown).")
    price = round(float(raw), 2)
    if price < 0:
        raise ErrandError("Price should be zero or more, not negative.")
    return price


def group_by_store(items: list[ErrandItem]) -> dict[str, list[ErrandItem]]:
    """Group open items under each store tag they carry.

    An item tagged with two stores appears under both. Untagged items land in
    the NO_STORE bucket so nothing silently vanishes from the plan.
    """
    grouped: dict[str, list[ErrandItem]] = {}
    for item in items:
        if item.stores:
            for store in item.stores:
                grouped.setdefault(store, []).append(item)
        else:
            grouped.setdefault(NO_STORE, []).append(item)
    return {name: grouped[name] for name in sorted(grouped, key=str.casefold)}


def store_tallies(items: list[ErrandItem]) -> list[tuple[str, int]]:
    """Count items per store tag, busiest store first (ties alphabetical).

    Used for the tally view: how long each store's list is right now.
    """
    counts: dict[str, int] = {}
    for item in items:
        if item.stores:
            for store in item.stores:
                counts[store] = counts.get(store, 0) + 1
        else:
            counts[NO_STORE] = counts.get(NO_STORE, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].casefold()))


def plan_run(
    open_items: list[ErrandItem], max_stops: int = 2
) -> tuple[list[tuple[str, list[ErrandItem]]], list[ErrandItem]]:
    """Pick one store combo (the 'one-plus-one' style run) and order its legs.

    Low-energy mode favors getting out the door once: the run is a single trip
    with at most `max_stops` stores (default 1 store, plus 1 backup). The
    combo is scored by how many open items it covers, so it chips away the
    list as much as possible while keeping leftover-aftenday items short.

    Returns (legs, leftover): legs are (store, items-that-store-can-cover) in
    visit order (busiest leg first), leftover holds items no leg can cover.
    """
    max_stops = parse_positive_int(max_stops, "max_stops", 2)
    if max_stops > MAX_STOPS_CAP:
        raise ErrandError(
            f"max_stops is capped at {MAX_STOPS_CAP}; this is a low-energy run."
        )
    if not open_items:
        return [], []

    taggable = [item for item in open_items if item.stores]
    untagged = [item for item in open_items if not item.stores]

    def covers(combo: tuple[str, ...]) -> set[str]:
        return {
            item.id
            for item in taggable
            if any(store in item.stores for store in combo)
        }

    stores = sorted(
        {store for item in taggable for store in item.stores},
        key=str.casefold,
    )
    best: tuple[str, ...] = ()
    best_ids: set[str] = set()
    for size in range(1, min(max_stops, len(stores) or 1) + 1):
        for combo in combinations(stores, size):
            ids = covers(combo)
            better = False
            if not best or len(ids) > len(best_ids):
                better = True
            elif len(ids) == len(best_ids) and len(combo) < len(best):
                better = True
            elif (
                len(ids) == len(best_ids)
                and len(combo) == len(best)
                and list(combo) < list(best)
            ):
                better = True
            if ids and better:
                best, best_ids = combo, ids

    if not best:
        return [], list(open_items)

    leg_items: dict[str, list[ErrandItem]] = {}
    for item in taggable:
        if item.id not in best_ids:
            continue
        hit = [store for store in best if store in item.stores]
        for store in hit or [best[0]]:
            leg_items.setdefault(store, []).append(item)

    legs = []
    for store in sorted(leg_items, key=lambda s: (-len(leg_items[s]), s.casefold())):
        legs.append((store, leg_items[store]))

    leftover = untagged + [item for item in taggable if item.id not in best_ids]
    return legs, leftover
