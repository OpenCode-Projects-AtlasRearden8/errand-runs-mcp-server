# Errand Runs MCP Server

A small, local-first MCP server that turns a scattered brain-dump of errands
into one doable trip. Log items with store tags, ask for a **single run** that
chips away as much of the list as possible while stopping at no more than a
couple of stores, close the items you actually bought, and pull a
**receipt** for the trip afterwards.

This is for the days when energy is scarce: the planner defaults to a
low-energy **one-plus-one mode** - one main stop, plus one backup store only
if it clearly helps. Items that don't fit are held for another day, which
keeps the plan short instead of turning it into an all-day adventure.

From [Asdale Dynamics, LLC](https://dylanasdale.github.io) - the
beginner-friendly AI education outfit behind *The Massive AI Manual*. All
data stays in a local JSON file: no cloud, no accounts, no uploads, no
secrets.

## What it does not do (on purpose)

- It is not a shopping-research tool: it never prices or compares products
  across the web. That is a different project's job.
- It is not a pantry tracker: it does not know what you already have at home.
  It only knows what you said you need and where you might buy it.

## Tools

| Tool | What it does |
| --- | --- |
| `log_item(item, stores, quantity, note)` | Log one errand item, tagged with the store(s) that can sell it, e.g. `["Canal Market", "Maple Drugstore"]`. |
| `tally()` | The open list grouped by store tag, with a count per store (busiest first). The "how long is each store's list?" view. |
| `plan_run(max_stops=2)` | One low-energy single-run plan: the store combo (default: one store plus one) that covers as much of the open list as possible, legs ordered busiest first, leftovers called out with a reason. |
| `mark_bought(item, price, store, bought_on)` | Close an item as bought (by id `I-3` or name). Price is optional. Multi-store items want to know which stop they came from. |
| `receipt(bought_on)` | After-the-fact closure query: what was bought that day, per-store subtotals, total paid, and where the open list stands. |
| `list_items(status)` | Double-check the log: `open` (default), `bought`, or `all`. |

Every result is plain, readable text an AI agent can act on.

## Getting started

Requires Python 3.10+.

```bash
pip install .
```

Wire it into your MCP client (Claude Code, codex, and friends) with a stdio
entry:

```json
{
  "mcpServers": {
    "errand-runs": {
      "command": "errand-runs-server"
    }
  }
}
```

Or run it straight from a checkout:

```bash
python -m errand_runs.server
```

Setting `ERRANDS_PATH=/some/where/errands.json` moves the data file; by
default it lives at `data/errands.json` inside the project.

## Suggested flow

1. **Dump the list** - one `log_item` per thing, tagging each with the store
   or stores that can sell it. Duplicate tags (`["Canal Market",
   "canal market"]`) collapse into one; untagged items are kept aside where
   they cannot silently vanish.
2. **Ask `tally`** - see how far ahead you are.
3. **Ask `plan_run`** - get the one trip: legs in visit order, items per
   leg with ids, plus whatever was left for another day and why.
4. **Go do it.** Come back when you're on the couch.
5. **Close the run** - `mark_bought` each item you got (price optional).
6. **Pull the `receipt`** - subtotals per store, the day's total, what
   still needs doing.

## Example

```text
> log_item(item="oat milk", stores=["Canal Market", "Maple Drugstore"])
Logged I-1: oat milk x1, tagged for Canal Market, Maple Drugstore. It is on the open list.

> plan_run()
One low-energy run (up to 2 stops) covers 8 of 8 open items.
Suggested order - busiest stop first:
  Leg 1 - Canal Market (4 items)
    - oat milk x1  [I-1]
    ...
Left off this run (rubber bands x2) - no stop combo within the limit covers them.
After the run, close each item with mark_bought, then pull the day's summary with receipt.

> receipt()
Receipt for 2026-11-07: 4 item(s) bought.
  I-1  oat milk x1  Canal Market  $4.25
  ...
Subtotal - Canal Market: $9.15
Total paid: $9.15.
Still open: 1 item(s) - BigBox Mart 1.
```

## Development

```bash
pip install -e .
pytest
```

The test suite covers grouping items by store tag and the per-store tallies,
the one-plus-one run planner, persistence, and every tool through the real
MCP server over stdio.

## License

MIT - see [LICENSE](LICENSE). Copyright (c) 2026 Asdale Dynamics, LLC.

More beginner-friendly AI guides and tools: [dylanasdale.github.io](https://dylanasdale.github.io).
