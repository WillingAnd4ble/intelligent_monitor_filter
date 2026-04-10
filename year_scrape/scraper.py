"""
Bulk ArXiv scraper: fetches ALL cs.AI papers from the past 365 days.

ArXiv API returns max 200 results per request, so we paginate with
start/max_results offsets and respect the 5-second rate limit.

Output: data/papers.jsonl — one JSON object per line, ~10-15k papers.

Usage:
    python scraper.py                    # default: cs.AI, last 365 days
    python scraper.py --category cs.LG   # different category
    python scraper.py --days 180         # last 180 days
"""

import json
import time
import logging
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

NAMESPACE = {"atom": "http://www.w3.org/2005/Atom"}


def fetch_page(query: str, start: int, page_size: int) -> list[dict]:
    """Fetch one page of results from the ArXiv API."""
    url = (
        f"http://export.arxiv.org/api/query?"
        f"search_query={query}&start={start}&max_results={page_size}"
        f"&sortBy=submittedDate&sortOrder=descending"
    )

    req = urllib.request.Request(url, headers={
        "User-Agent": "ArXivYearScraper/1.0 (academic thesis; mailto:noreply@example.com)"
    })

    try:
        response = urllib.request.urlopen(req, timeout=30)
        xml_data = response.read()
    except Exception as e:
        logger.error(f"HTTP error at start={start}: {e}")
        return []

    root = ET.fromstring(xml_data)
    papers = []

    for entry in root.findall("atom:entry", NAMESPACE):
        paper_id_raw = entry.find("atom:id", NAMESPACE).text
        paper_id = paper_id_raw.split("/")[-1]

        title = entry.find("atom:title", NAMESPACE).text.replace("\n", " ").strip()
        abstract = entry.find("atom:summary", NAMESPACE).text.replace("\n", " ").strip()
        published_str = entry.find("atom:published", NAMESPACE).text
        published_at = datetime.fromisoformat(published_str.replace("Z", "+00:00"))

        authors = [
            a.find("atom:name", NAMESPACE).text
            for a in entry.findall("atom:author", NAMESPACE)
        ]

        pdf_url = None
        for link in entry.findall("atom:link", NAMESPACE):
            if link.attrib.get("title") == "pdf":
                pdf_url = link.attrib.get("href")
                break

        papers.append({
            "paper_id": paper_id,
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "published_at": published_at.isoformat(),
            "pdf_url": pdf_url,
            "source_url": paper_id_raw,
        })

    return papers


def scrape_year(
    category: str = None,
    days: int = 365,
    page_size: int = None,
    output_path: Path = None,
):
    """
    Paginate through ArXiv and save all papers to JSONL.

    Stops when: we've paged through everything ArXiv returns,
    or the oldest paper is older than `days` days.
    """
    category = category or config.ARXIV_CATEGORY
    page_size = page_size or config.ARXIV_PAGE_SIZE
    output_path = output_path or config.PAPERS_JSONL
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    query = f"cat:{category}"

    total_saved = 0
    start = 0
    seen_ids = set()

    # Load existing IDs to allow resuming
    if output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            for line in f:
                obj = json.loads(line)
                seen_ids.add(obj["paper_id"])
        total_saved = len(seen_ids)
        logger.info(f"Resuming: {total_saved} papers already in {output_path.name}")

    with open(output_path, "a", encoding="utf-8") as f:
        while True:
            logger.info(f"Fetching page start={start}, page_size={page_size} ...")
            papers = fetch_page(query, start, page_size)

            if not papers:
                logger.info("Empty page returned, stopping.")
                break

            new_count = 0
            oldest_in_page = None

            for p in papers:
                pub_date = datetime.fromisoformat(p["published_at"])
                if oldest_in_page is None or pub_date < oldest_in_page:
                    oldest_in_page = pub_date

                if p["paper_id"] in seen_ids:
                    continue

                seen_ids.add(p["paper_id"])
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
                new_count += 1

            total_saved += new_count
            logger.info(
                f"  Got {len(papers)} papers, {new_count} new. "
                f"Total: {total_saved}. Oldest in page: {oldest_in_page}"
            )

            # Stop if we've gone past the cutoff date
            if oldest_in_page and oldest_in_page < cutoff:
                logger.info(f"Reached cutoff date {cutoff.date()}, stopping.")
                break

            # Stop if ArXiv returned fewer than requested (last page)
            if len(papers) < page_size:
                logger.info("Partial page — end of results.")
                break

            start += page_size
            time.sleep(config.ARXIV_DELAY_SECONDS)

    logger.info(f"Done. Total papers saved: {total_saved} → {output_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape ArXiv papers for the past year")
    parser.add_argument("--category", default=None, help="ArXiv category (default: cs.AI)")
    parser.add_argument("--days", type=int, default=365, help="How many days back to scrape")
    parser.add_argument("--page-size", type=int, default=None, help="Results per API call (max 200)")
    args = parser.parse_args()

    scrape_year(category=args.category, days=args.days, page_size=args.page_size)