"""Errand runs helper: an MCP server for logging errands, planning one
low-energy store run, and pulling a receipt for the trip afterwards.

All data stays in a local JSON file - no cloud, no accounts.
"""

from .errands import ErrandError, ErrandItem, group_by_store, plan_run, store_tallies
from .store import ErrandStore

__all__ = [
    "ErrandError",
    "ErrandItem",
    "ErrandStore",
    "group_by_store",
    "plan_run",
    "store_tallies",
]
