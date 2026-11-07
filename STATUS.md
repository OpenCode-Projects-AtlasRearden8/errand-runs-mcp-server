# STATUS.md - errand-runs-mcp-server

## What was built

A small local-first MCP server (`errand-runs-mcp-server`, Python package
`errand_runs`) that turns a scattered errand list into one doable trip.

- **`log_item(item, stores, quantity, note)`** - log one item, tagged with
  the store(s) that can sell it. Duplicate tags collapse
  case-insensitively; untagged items are kept in a visible "(no store
  tagged)" bucket instead of being lost.
- **`tally()`** - the open list grouped by store tag with a count per store,
  busiest store first.
- **`plan_run(max_stops=2)`** - one low-energy single-run plan in
  "one-plus-one" mode: the store combo (default one main stop plus one
  backup) that chips away the most of the open list, legs ordered busiest
  first, leftovers explained (needs a tag / beyond the stop limit).
- **`mark_bought(item, price, store, bought_on)`** - close an item as
  bought (by id or name, price optional, multi-store items name the stop).
- **`receipt(bought_on)`** - after-the-fact closure query: what was bought
  that day, per-store subtotals, total paid, what is still open.
- **`list_items(status)`** - double-check the log (open / bought / all).

Data lives in one JSON file (`data/errands.json`, override with
`ERRANDS_PATH`), written atomically (temp file + rename). Results are plain,
agent-friendly text. No network calls, no secrets, no personal data =
synthetic store names only (e.g. "Canal Market").

Distinct from: **shopping-research-with-ai-guide** (web research) and
**pantry-inventory-mcp-server** (home stock). This one is purely "what do I
need to go get, and how do I do it in one low-energy trip".

## How to run it

```bash
pip install .            # or: pip install -e .
errand-runs-server       # console script, stdio transport
# or:
python -m errand_runs.server
```

Point your MCP client at it over stdio with `command: errand-runs-server`.
Development checks: `pytest`.

## Verification results

- `pip install -e .` - clean install; console script `errand-runs-server`
  created and boots (`errand-runs MCP server (2.x) starting on stdio...`).
- `python -m errand_runs.server` - boots and serves over stdio.
- **`pytest`: 59 passed, 0 failed** (Python 3.13, `mcp` 2.3.0). Coverage
  includes:
  - grouping items by store tag (multi-tag items appear under each tag;
    untagged items bucketed; tag dedupe is case-insensitive)
  - per-store tallies (busy-first ordering, tie-break alphabetical, open
    items only)
  - the one-plus-one planner (best pair covers all tagged items, single-stop
    mode, alphabetical tie-break, leftover reasons, stop cap)
  - store persistence (reload roundtrip, next-id continuity, atomic pretty
    JSON, corrupt-file error is readable)
  - every tool through the real MCP server, plus a stdio subprocess
    roundtrip using the official `mcp` client (list tools, log, tally,
    plan, close, receipt)

## Known gaps

- `plan_run` considers item counts, not quantities or store hours/geo; the
  visit order is "busiest leg first", not drive-time aware.
- A price is per receipt line (what you paid), not unit-price aware, so
  quantity does not multiply into the subtotal.
- Receipt totals ignore unpriced items and say so explicitly.
- Only stdio transport is wired (no HTTP/SSE).
- No packaging beyond the basics published to any registry - it is meant to
  be pip-installed from a local checkout.
- Tool errors (unknown item, ambiguous match, missing store on multi-store
  items) are returned as friendly text, leaving "what to do next" to the
  calling agent.

## License

MIT - Copyright (c) 2026 Asdale Dynamics, LLC. See `LICENSE`. Part of the
Asdale Dynamics, LLC beginner-friendly AI tools collection
(dylanasdale.github.io).
