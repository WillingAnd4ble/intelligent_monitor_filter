import time
import logging
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from sqlalchemy import func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Paper
from app.worker.modal_client import specter2_embed_batch

logger = logging.getLogger(__name__)

# ArXiv Terms of Use: minimum 3.1 seconds between API requests
_ARXIV_DELAY_SECONDS = 5
_last_arxiv_request_time: float = 0.0

# arXiv API per-request maximum (their hard limit, not ours)
ARXIV_PAGE_SIZE = 200

# Safety valve for windowed scrapes — never reached in normal use.
# Trips on bugs (T_0 resolved to 1970, infinite-loop) or extreme
# real-world spikes that warrant a manual look.
ARXIV_WINDOW_HARD_CAP = 5000


def _throttle_arxiv():
    """Enforce minimum delay between ArXiv API requests."""
    global _last_arxiv_request_time
    elapsed = time.monotonic() - _last_arxiv_request_time
    if _last_arxiv_request_time > 0 and elapsed < _ARXIV_DELAY_SECONDS:
        wait = _ARXIV_DELAY_SECONDS - elapsed
        logger.info(f"ArXiv rate limit: sleeping {wait:.1f}s")
        time.sleep(wait)
    _last_arxiv_request_time = time.monotonic()


def _build_query_url(search_query: str, start: int, page_size: int) -> str:
    """Build an arXiv API query URL.

    arXiv's API uses `+` as a literal token separator inside search_query
    (= URL-decoded space), so we must NOT urlencode the query as a whole.
    Brackets and parens, however, must be percent-encoded — the API rejects
    raw `[ ] ( )` sporadically and the docs always show them encoded.
    """
    safe_query = (
        search_query
        .replace("[", "%5B")
        .replace("]", "%5D")
        .replace("(", "%28")
        .replace(")", "%29")
    )
    return (
        "http://export.arxiv.org/api/query?"
        f"search_query={safe_query}"
        f"&start={start}&max_results={page_size}"
        "&sortBy=submittedDate&sortOrder=descending"
    )


def _fetch_and_parse(url: str) -> list[dict]:
    """HTTP GET + Atom-XML parse → list of paper dicts. [] on error."""
    logger.debug(f"ArXiv GET {url}")
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "ArXivFilterBot/1.0 (academic thesis project; mailto:noreply@example.com)"
        })
        response = urllib.request.urlopen(req)
        xml_data = response.read()
    except Exception as e:
        logger.error(f"ArXiv Fetch Exception: {e} (url={url})")
        return []

    root = ET.fromstring(xml_data)
    namespace = {'atom': 'http://www.w3.org/2005/Atom'}

    papers = []
    for entry in root.findall('atom:entry', namespace):
        paper_id = entry.find('atom:id', namespace).text.split('/')[-1]
        title = entry.find('atom:title', namespace).text.replace('\n', ' ').strip()
        abstract = entry.find('atom:summary', namespace).text.replace('\n', ' ').strip()
        published_str = entry.find('atom:published', namespace).text
        published_at = datetime.fromisoformat(published_str.replace("Z", "+00:00"))

        authors = [author.find('atom:name', namespace).text for author in entry.findall('atom:author', namespace)]

        pdf_url = None
        for link in entry.findall('atom:link', namespace):
            if link.attrib.get('title') == 'pdf':
                pdf_url = link.attrib.get('href')
                break

        papers.append({
            "id": paper_id,
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "published_at": published_at,
            "pdf_url": pdf_url,
            "source_url": entry.find('atom:id', namespace).text.replace("http://", "https://")
        })

    return papers


def fetch_arxiv_papers(
    query: str = "cat:cs.AI",
    since: datetime | None = None,
    until: datetime | None = None,
    max_results: int = 50,
) -> list[dict]:
    """Fetch papers from the arXiv API.

    Two modes:

    Windowed (preferred): pass `since` and `until` as UTC datetimes.
        Builds `(query) AND submittedDate:[since TO until]`, paginates
        200/page until empty. Hard-stops at ARXIV_WINDOW_HARD_CAP=5000
        as a safety valve (logs a warning if hit).

    Count-bounded (legacy): pass `max_results`. Single fetch of newest
        N papers under `query`. Kept for callers that haven't migrated.
    """
    if since is None or until is None:
        _throttle_arxiv()
        url = _build_query_url(query, start=0, page_size=max_results)
        return _fetch_and_parse(url)

    if since >= until:
        return []

    s = since.astimezone(timezone.utc).strftime("%Y%m%d%H%M")
    u = until.astimezone(timezone.utc).strftime("%Y%m%d%H%M")
    windowed_query = f"({query})+AND+submittedDate:[{s}+TO+{u}]"

    all_papers: list[dict] = []
    seen_ids: set[str] = set()
    start = 0

    while True:
        if len(all_papers) >= ARXIV_WINDOW_HARD_CAP:
            logger.warning(
                f"ArXiv windowed fetch hit safety cap of {ARXIV_WINDOW_HARD_CAP} "
                f"papers for window [{since.isoformat()} -> {until.isoformat()}], "
                f"query={query!r}. Stopping. Investigate before raising the cap."
            )
            break

        _throttle_arxiv()
        url = _build_query_url(windowed_query, start=start, page_size=ARXIV_PAGE_SIZE)
        page = _fetch_and_parse(url)
        if not page:
            break

        new_in_page = 0
        for p in page:
            if p["id"] in seen_ids:
                continue
            seen_ids.add(p["id"])
            all_papers.append(p)
            new_in_page += 1

        # Partial page = end of results. All-duplicates page = arXiv pagination
        # quirk where start>=total can echo the last page; treat as terminal.
        if len(page) < ARXIV_PAGE_SIZE or new_in_page == 0:
            break

        start += ARXIV_PAGE_SIZE

    logger.info(
        f"ArXiv windowed fetch: {len(all_papers)} papers in "
        f"[{since.isoformat()} -> {until.isoformat()}], query={query!r}"
    )
    return all_papers

async def ingest_papers(session: AsyncSession, papers_data: list[dict]):
    """Ingest scraped papers and generate SPECTER2 embeddings via Modal GPU."""
    # Collect papers that don't exist yet
    new_papers = []
    for p_data in papers_data:
        paper_exists = await session.get(Paper, p_data["id"])
        if not paper_exists:
            new_papers.append(p_data)

    if not new_papers:
        return

    # Batch call Modal SPECTER2 for all new papers at once
    embeddings = await specter2_embed_batch([
        {"title": p["title"], "abstract": p["abstract"]} for p in new_papers
    ])

    for p_data, embedding in zip(new_papers, embeddings):
        new_paper = Paper(
            id=p_data["id"],
            title=p_data["title"],
            authors=p_data["authors"],
            abstract=p_data["abstract"],
            published_at=p_data["published_at"],
            pdf_url=p_data["pdf_url"],
            source_url=p_data["source_url"],
            embedding=embedding,
        )
        session.add(new_paper)

    await session.flush()

    # Populate TSVECTOR search_vector for BM25 lexical search leg of RRF
    paper_ids = [p["id"] for p in new_papers]
    await session.execute(
        Paper.__table__.update()
        .where(Paper.id.in_(paper_ids))
        .values(search_vector=sa_func.to_tsvector(
            "english",
            sa_func.concat(Paper.title, " ", Paper.abstract)
        ))
    )

    await session.commit()
