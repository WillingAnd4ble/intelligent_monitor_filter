import time
import logging
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from sqlalchemy import func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Paper
from app.worker.modal_client import specter2_embed_batch

logger = logging.getLogger(__name__)

# ArXiv Terms of Use: minimum 3.1 seconds between API requests
_ARXIV_DELAY_SECONDS = 5
_last_arxiv_request_time: float = 0.0

def _throttle_arxiv():
    """Enforce minimum delay between ArXiv API requests."""
    global _last_arxiv_request_time
    elapsed = time.monotonic() - _last_arxiv_request_time
    if _last_arxiv_request_time > 0 and elapsed < _ARXIV_DELAY_SECONDS:
        wait = _ARXIV_DELAY_SECONDS - elapsed
        logger.info(f"ArXiv rate limit: sleeping {wait:.1f}s")
        time.sleep(wait)
    _last_arxiv_request_time = time.monotonic()

def fetch_arxiv_papers(query: str = "cat:cs.AI", max_results: int = 50) -> list[dict]:
    """Basic XML extraction targeting external ArXiv APIs organically without bloated package mapping overhead."""
    _throttle_arxiv()

    url = f"http://export.arxiv.org/api/query?search_query={query}&start=0&max_results={max_results}&sortBy=submittedDate&sortOrder=descending"

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "ArXivFilterBot/1.0 (academic thesis project; mailto:noreply@example.com)"
        })
        response = urllib.request.urlopen(req)
        xml_data = response.read()
    except Exception as e:
        logger.error(f"ArXiv Fetch Exception: {e}")
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
            "source_url": entry.find('atom:id', namespace).text
        })
        
    return papers

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
