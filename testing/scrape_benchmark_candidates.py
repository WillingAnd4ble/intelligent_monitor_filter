"""
Scrape the latest 200 ArXiv papers for benchmark dataset construction.

Reuses the project's existing ArXiv Atom-XML technique
(year_scrape.scraper.fetch_page), which is the same parser used in
backend/app/worker/arxiv_scraper.py.

Output: testing/data/candidates/papers_<category>_<UTC-timestamp>.jsonl
        — one JSON object per line, ready for manual relevance labeling.

Usage:
    python testing/scrape_benchmark_candidates.py
    python testing/scrape_benchmark_candidates.py --category cs.LG
    python testing/scrape_benchmark_candidates.py --count 100 --category cs.AI
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parent
YEAR_SCRAPE_DIR = REPO_ROOT / "year_scrape"
# year_scrape uses flat sibling imports (`import config`), so its own dir
# must be on sys.path — putting only the repo root is not enough.
sys.path.insert(0, str(YEAR_SCRAPE_DIR))

from scraper import fetch_page  # noqa: E402
import config as year_scrape_config  # noqa: E402


def scrape_latest(category: str, count: int, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)

    query = f"cat:{category}"
    papers: list[dict] = []
    start = 0
    page_size = 200  # ArXiv API hard max per request

    while len(papers) < count:
        remaining = count - len(papers)
        batch_size = min(page_size, remaining)
        print(f"Fetching start={start} size={batch_size} ...")
        batch = fetch_page(query, start=start, page_size=batch_size)
        if not batch:
            print("Empty page — stopping early.")
            break
        papers.extend(batch)
        if len(batch) < batch_size:
            print("Partial page — end of results.")
            break
        start += batch_size
        if len(papers) < count:
            time.sleep(year_scrape_config.ARXIV_DELAY_SECONDS)

    papers = papers[:count]

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = out_dir / f"papers_{category.replace('.', '-')}_{timestamp}.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for p in papers:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    print(f"\nSaved {len(papers)} papers -> {out_path}")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape latest ArXiv papers for benchmark labeling")
    parser.add_argument("--category", default="cs.AI", help="ArXiv category (default: cs.AI)")
    parser.add_argument("--count", type=int, default=200, help="How many papers to fetch (default: 200)")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=THIS_DIR / "data" / "candidates",
        help="Output directory (default: testing/data/candidates/)",
    )
    args = parser.parse_args()

    scrape_latest(args.category, args.count, args.out_dir)
