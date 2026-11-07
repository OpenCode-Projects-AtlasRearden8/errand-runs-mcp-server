"""Persistence for the errands tracker: one JSON file, all local.

The store keeps a list of logged items on disk and hands back domain
objects from errands.py. Every change is written atomically (temp file +
rename) so a crash mid-write cannot corrupt the data.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .errands import (
    BOUGHT,
    ErrandError,
    ErrandItem,
    OPEN,
    clean_name,
    clean_stores,
    normalize_name,
    parse_date,
    parse_positive_int,
    parse_price,
)

DEFAULT_ITEM_ID_PREFIX = "I-"


def _blank_data() -> dict[str, Any]:
    """Fresh empty store contents (per call, so nothing is shared)."""
    return {"items": [], "next_item_id": 1}


@dataclass
class ErrandStore:
    path: Path

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self._today: Callable[[], date] = date.today
        self._data: dict[str, Any] = {}
        self._load()

    # ---------------------------------------------------------------- time
    def today(self) -> date:
        """Reference date overrideable in tests."""
        return self._today()

    # --------------------------------------------------------------- disk
    def _load(self) -> None:
        if not self.path.exists():
            self._data = _blank_data()
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ErrandError(
                f"Could not read the errands file at {self.path}: {exc}. "
                "Fix or remove the file and try again."
            ) from exc
        if not isinstance(raw, dict):
            raise ErrandError(
                f"The errands file at {self.path} is not valid JSON object data."
            )
        data = _blank_data()
        data["next_item_id"] = raw.get("next_item_id", 1)
        for entry in raw.get("items", []):
            stores = clean_stores(entry.get("stores"))
            bought_raw = entry.get("bought_on")
            price = entry.get("price")
            item = ErrandItem(
                id=str(entry.get("id", "")),
                name=clean_name(entry.get("name", "")),
                stores=stores,
                quantity=parse_positive_int(entry.get("quantity", 1), "quantity", 1),
                note=str(entry.get("note", "")),
                status=BOUGHT if entry.get("status") == BOUGHT else OPEN,
                logged=parse_date(str(entry.get("logged", date.today().isoformat()))),
                bought_on=parse_date(str(bought_raw)) if bought_raw else None,
                bought_store=(
                    str(entry["bought_store"]) if entry.get("bought_store") else None
                ),
                price=parse_price(price) if price is not None else None,
            )
            data["items"].append(item)
        self._data = data

    def _save(self) -> None:
        payload = {
            "items": [
                {
                    "id": item.id,
                    "name": item.name,
                    "stores": item.stores,
                    "quantity": item.quantity,
                    "note": item.note,
                    "status": item.status,
                    "logged": item.logged.isoformat(),
                    "bought_on": item.bought_on.isoformat() if item.bought_on else None,
                    "bought_store": item.bought_store,
                    "price": item.price,
                }
                for item in self._data["items"]
            ],
            "next_item_id": self._data["next_item_id"],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=self.path.parent, delete=False
        )
        try:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        finally:
            handle.close()
        os.replace(handle.name, self.path)

    # -------------------------------------------------------------- items
    def add_item(
        self,
        name: str,
        stores: list[str] | None = None,
        quantity: int = 1,
        note: str = "",
    ) -> ErrandItem:
        """Log a new open item tagged with the stores that can sell it."""
        item = ErrandItem(
            id=f"{DEFAULT_ITEM_ID_PREFIX}{self._data['next_item_id']}",
            name=clean_name(name),
            stores=clean_stores(stores),
            quantity=parse_positive_int(quantity, "quantity", 1),
            note=str(note or "").strip(),
            status=OPEN,
            logged=self.today(),
        )
        self._data["next_item_id"] += 1
        self._data["items"].append(item)
        self._save()
        return item

    def all_items(self) -> list[ErrandItem]:
        """Everything on file, oldest first."""
        return list(self._data["items"])

    def open_items(self) -> list[ErrandItem]:
        """Items still waiting to be bought."""
        return [item for item in self._data["items"] if item.status == OPEN]

    def bought_on(self, day: date) -> list[ErrandItem]:
        """Items closed with a purchase on a given day."""
        return [
            item
            for item in self._data["items"]
            if item.status == BOUGHT and item.bought_on == day
        ]

    def find_item(self, query: str) -> ErrandItem:
        """Match an item by id (I-3) or by name (case-insensitive).

        Exact name wins; otherwise a unique substring match is accepted.
        Ambiguous substrings ask the caller to be more specific.
        """
        if not isinstance(query, str) or not query.strip():
            raise ErrandError(
                "Pick an item by id (like I-3) or name (like 'oat milk')."
            )
        needle = query.strip()
        for item in self._data["items"]:
            if item.id.upper() == needle.upper():
                return item
        key = normalize_name(needle)
        exact = [
            item for item in self._data["items"] if normalize_name(item.name) == key
        ]
        if len(exact) == 1:
            return exact[0]
        if len(exact) > 1:
            names = ", ".join(f"{i.id} {i.name}" for i in exact)
            raise ErrandError(f"Several items match {needle!r} ({names}). Use an id.")
        partial = [item for item in self._data["items"] if key in normalize_name(item.name)]
        if len(partial) == 1:
            return partial[0]
        if len(partial) > 1:
            names = ", ".join(f"{i.id} {i.name}" for i in partial)
            raise ErrandError(f"Several items match {needle!r} ({names}). Use an id.")
        raise ErrandError(
            f"No logged item matches {needle!r}. Try `tally` to see what is on file."
        )

    def mark_bought(
        self,
        item: ErrandItem,
        on: str | None = None,
        store: str | None = None,
        price: float | None = None,
    ) -> ErrandItem:
        """Close an item with the purchase date, store, and optional price."""
        if item.status == BOUGHT:
            raise ErrandError(
                f"{item.id} {item.name} was already bought on "
                f"{item.bought_on.isoformat() if item.bought_on else '?'}."
            )
        store = " ".join(store.split()) if store and store.strip() else ""
        if not store and len(item.stores) == 1:
            store = item.stores[0]
        elif not store and len(item.stores) > 1:
            raise ErrandError(
                f"{item.name} is tagged with several stores "
                f"({', '.join(item.stores)}). Say which store it came from."
            )
        bought = self.today() if not on else parse_date(on)
        item.status = BOUGHT
        item.bought_on = bought
        item.bought_store = store or None
        item.price = parse_price(price)
        self._save()
        return item
