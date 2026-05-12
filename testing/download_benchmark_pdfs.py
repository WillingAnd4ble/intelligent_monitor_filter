"""
Download raw PDFs for the benchmark candidate set.

Reads a candidates JSONL produced by `scrape_benchmark_candidates.py` and
downloads each paper's PDF into `testing/data/candidates/pdfs/<paper_id>.pdf`.

Behaviour:
  - resumes: files that already exist on disk are skipped
  - rate-limited: ArXiv asks ~3s between PDF requests
  - same User-Agent header as the project's other ArXiv clients

Usage:
    python testing/download_benchmark_pdfs.py
        # picks the newest papers_*.jsonl in testing/data/candidates/

    python testing/download_benchmark_pdfs.py --jsonl testing/data/candidates/papers_cs-AI_20260505T192402Z.jsonl
    python testing/download_benchmark_pdfs.py --limit 50
    python testing/download_benchmark_pdfs.py --delay 3.0
"""

import argparse
import json
import time
import urllib.request
import urllib.error
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
DEFAULT_CANDIDATES_DIR = THIS_DIR / "data" / "candidates"
DEFAULT_PDF_DIR = DEFAULT_CANDIDATES_DIR / "pdfs"

USER_AGENT = "ArXivYearScraper/1.0 (academic thesis; mailto:noreply@example.com)"


def newest_jsonl(candidates_dir: Path) -> Path:
    files = sorted(candidates_dir.glob("papers_*.jsonl"))
    if not files:
        raise SystemExit(f"No papers_*.jsonl found in {candidates_dir}")
    return files[-1]


def safe_filename(paper_id: str) -> str:
    return paper_id.replace("/", "_") + ".pdf"


def download_one(pdf_url: str, dest: Path, timeout: int = 60) -> bool:
    req = urllib.request.Request(pdf_url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"  ! {pdf_url} -> {e}")
        return False

    tmp = dest.with_suffix(".pdf.part")
    tmp.write_bytes(data)
    tmp.rename(dest)
    return True


def main():
    parser = argparse.ArgumentParser(description="Download raw PDFs for benchmark candidates")
    parser.add_argument("--jsonl", type=Path, default=None, help="Input papers JSONL (default: newest in testing/data/candidates/)")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_PDF_DIR, help="Where to write PDFs (default: testing/data/candidates/pdfs/)")
    parser.add_argument("--limit", type=int, default=None, help="Stop after N papers (default: all)")
    parser.add_argument("--delay", type=float, default=3.0, help="Seconds to wait between PDF requests (default: 3.0)")
    args = parser.parse_args()

    jsonl = args.jsonl or newest_jsonl(DEFAULT_CANDIDATES_DIR)
    print(f"Reading: {jsonl}")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    with open(jsonl, "r", encoding="utf-8") as f:
        papers = [json.loads(line) for line in f if line.strip()]
    if args.limit:
        papers = papers[: args.limit]
    print(f"Target: {len(papers)} papers -> {args.out_dir}")

    downloaded = 0
    skipped = 0
    failed = 0

    for i, p in enumerate(papers, 1):
        paper_id = p["paper_id"]
        pdf_url = p.get("pdf_url")
        if not pdf_url:
            print(f"[{i}/{len(papers)}] {paper_id}: no pdf_url, skipping")
            failed += 1
            continue

        dest = args.out_dir / safe_filename(paper_id)
        if dest.exists() and dest.stat().st_size > 0:
            skipped += 1
            continue

        print(f"[{i}/{len(papers)}] {paper_id} <- {pdf_url}")
        ok = download_one(pdf_url, dest)
        if ok:
            downloaded += 1
        else:
            failed += 1

        if i < len(papers) and args.delay > 0:
            time.sleep(args.delay)

    print(f"\nDone. downloaded={downloaded}  skipped(existing)={skipped}  failed={failed}")
    print(f"PDFs in: {args.out_dir}")


if __name__ == "__main__":
    main()
