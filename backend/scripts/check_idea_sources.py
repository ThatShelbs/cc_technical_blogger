"""Read every feed in the Idea Lab source catalog once and report which ones answer.

Run after editing ``src/proseferno/idealab/catalog.json``:

    uv run python scripts/check_idea_sources.py            # every source, switched on or not
    uv run python scripts/check_idea_sources.py --titles   # also print the first few titles of each

Goes online (plain GETs to public feeds, no keys, nothing personal). Exits 1 if a source failed.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime, timedelta

from proseferno.idealab.collect import HttpSignalCollector
from proseferno.idealab.sources import SourceChanges, build_config


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--titles", action="store_true", help="print the first three titles of each source")
    parser.add_argument("--days", type=int, default=14, help="how many days back to look (default 14)")
    args = parser.parse_args()

    sources = build_config(SourceChanges()).sources
    since = datetime.now(UTC) - timedelta(days=args.days)
    signals, health = await HttpSignalCollector().collect(sources, since=since)
    names = {s.id: s.name for s in sources}
    failed = 0
    for result in health:
        mark = "ok  " if result.ok else "FAIL"
        failed += not result.ok
        print(f"{mark} {result.count:>3}  {names[result.source_id]}" + (f"  ({result.error})" if result.error else ""))
        if args.titles:
            for signal in [s for s in signals if s.source_id == result.source_id][:3]:
                print(f"           - {signal.title[:100]}")
    print(f"\n{len(signals)} items from {len(health) - failed} of {len(health)} sources.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
