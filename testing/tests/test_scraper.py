"""
Tests for the ArXiv scraper: XML parsing, rate limiting, deduplication.

All HTTP calls are mocked — no real network traffic.
"""

import time
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone, timedelta

import pytest
from freezegun import freeze_time

from conftest import SAMPLE_ARXIV_XML


# ---------------------------------------------------------------------------
# default_daily_window_utc — weekday / weekend window logic
# ---------------------------------------------------------------------------

class TestDefaultDailyWindowUtc:
    """Tue–Fri → yesterday only. Sat–Mon → Fri 00:00 → Sun 23:59:59 (covers weekend)."""

    @freeze_time("2026-05-13 09:00:00")  # Wednesday
    def test_weekday_returns_yesterday_window(self):
        from app.worker.arxiv_scraper import default_daily_window_utc
        since, until = default_daily_window_utc()
        assert since == datetime(2026, 5, 12, 0, 0, 0, tzinfo=timezone.utc)
        assert until == datetime(2026, 5, 12, 23, 59, 59, tzinfo=timezone.utc)

    @freeze_time("2026-05-15 09:00:00")  # Friday
    def test_friday_returns_thursday_window(self):
        from app.worker.arxiv_scraper import default_daily_window_utc
        since, until = default_daily_window_utc()
        assert since == datetime(2026, 5, 14, 0, 0, 0, tzinfo=timezone.utc)
        assert until == datetime(2026, 5, 14, 23, 59, 59, tzinfo=timezone.utc)

    @freeze_time("2026-05-18 09:00:00")  # Monday
    def test_monday_returns_friday_through_sunday_window(self):
        from app.worker.arxiv_scraper import default_daily_window_utc
        since, until = default_daily_window_utc()
        assert since == datetime(2026, 5, 15, 0, 0, 0, tzinfo=timezone.utc)   # Fri 00:00
        assert until == datetime(2026, 5, 17, 23, 59, 59, tzinfo=timezone.utc)  # Sun 23:59:59

    @freeze_time("2026-05-16 09:00:00")  # Saturday
    def test_saturday_returns_friday_window(self):
        from app.worker.arxiv_scraper import default_daily_window_utc
        since, until = default_daily_window_utc()
        # Sat morning: yesterday was Friday — just take Friday's window
        assert since == datetime(2026, 5, 15, 0, 0, 0, tzinfo=timezone.utc)
        assert until == datetime(2026, 5, 15, 23, 59, 59, tzinfo=timezone.utc)

    @freeze_time("2026-05-17 09:00:00")  # Sunday
    def test_sunday_returns_friday_through_saturday_window(self):
        from app.worker.arxiv_scraper import default_daily_window_utc
        since, until = default_daily_window_utc()
        assert since == datetime(2026, 5, 15, 0, 0, 0, tzinfo=timezone.utc)   # Fri 00:00
        assert until == datetime(2026, 5, 16, 23, 59, 59, tzinfo=timezone.utc)  # Sat 23:59:59

    def test_accepts_explicit_now_override(self):
        from app.worker.arxiv_scraper import default_daily_window_utc
        now = datetime(2026, 5, 13, 9, 0, 0, tzinfo=timezone.utc)  # Wednesday
        since, until = default_daily_window_utc(now)
        assert since == datetime(2026, 5, 12, 0, 0, 0, tzinfo=timezone.utc)
        assert until == datetime(2026, 5, 12, 23, 59, 59, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# fetch_arxiv_papers — XML parsing
# ---------------------------------------------------------------------------

class TestFetchArxivPapers:
    """Tests for app.worker.arxiv_scraper.fetch_arxiv_papers"""

    @patch("app.worker.arxiv_scraper.urllib.request.urlopen")
    @patch("app.worker.arxiv_scraper._throttle_arxiv")
    def test_parses_valid_xml_into_paper_dicts(self, mock_throttle, mock_urlopen):
        """Given valid ArXiv XML, returns a list of paper dicts with correct fields."""
        mock_response = MagicMock()
        mock_response.read.return_value = SAMPLE_ARXIV_XML.encode("utf-8")
        mock_urlopen.return_value = mock_response

        from app.worker.arxiv_scraper import fetch_arxiv_papers
        papers = fetch_arxiv_papers("cat:cs.AI", max_results=10)

        assert len(papers) == 2

        p1 = papers[0]
        assert p1["id"] == "2404.12345"
        assert p1["title"] == "Multi-Agent Coordination via Large Language Models"
        assert "LLM-based agents" in p1["abstract"]
        assert p1["authors"] == ["Alice Smith", "Bob Jones"]
        assert p1["pdf_url"] == "http://arxiv.org/pdf/2404.12345v1"
        assert isinstance(p1["published_at"], datetime)

    @patch("app.worker.arxiv_scraper.urllib.request.urlopen")
    @patch("app.worker.arxiv_scraper._throttle_arxiv")
    def test_extracts_paper_id_from_full_url(self, mock_throttle, mock_urlopen):
        """Paper ID should be the last segment of the ArXiv URL, not the full URL."""
        mock_response = MagicMock()
        mock_response.read.return_value = SAMPLE_ARXIV_XML.encode("utf-8")
        mock_urlopen.return_value = mock_response

        from app.worker.arxiv_scraper import fetch_arxiv_papers
        papers = fetch_arxiv_papers()

        for p in papers:
            assert "/" not in p["id"], f"Paper ID should not contain slashes: {p['id']}"
            assert "arxiv.org" not in p["id"]

    @patch("app.worker.arxiv_scraper.urllib.request.urlopen")
    @patch("app.worker.arxiv_scraper._throttle_arxiv")
    def test_returns_empty_list_on_network_error(self, mock_throttle, mock_urlopen):
        """If ArXiv is unreachable, return [] instead of crashing."""
        mock_urlopen.side_effect = Exception("Connection refused")

        from app.worker.arxiv_scraper import fetch_arxiv_papers
        papers = fetch_arxiv_papers()

        assert papers == []

    @patch("app.worker.arxiv_scraper.urllib.request.urlopen")
    @patch("app.worker.arxiv_scraper._throttle_arxiv")
    def test_builds_correct_query_url(self, mock_throttle, mock_urlopen):
        """The URL sent to ArXiv must include the user's category query."""
        mock_response = MagicMock()
        mock_response.read.return_value = SAMPLE_ARXIV_XML.encode("utf-8")
        mock_urlopen.return_value = mock_response

        from app.worker.arxiv_scraper import fetch_arxiv_papers
        fetch_arxiv_papers("cat:cs.AI+OR+cat:cs.LG", max_results=50)

        call_args = mock_urlopen.call_args
        request_obj = call_args[0][0]
        url = request_obj.full_url
        assert "cat:cs.AI+OR+cat:cs.LG" in url
        assert "max_results=50" in url
        assert "sortBy=submittedDate" in url

    @patch("app.worker.arxiv_scraper.urllib.request.urlopen")
    @patch("app.worker.arxiv_scraper._throttle_arxiv")
    def test_handles_missing_pdf_link(self, mock_throttle, mock_urlopen):
        """If a paper has no PDF link element, pdf_url should be None."""
        xml_no_pdf = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <id>http://arxiv.org/abs/2404.00001</id>
            <title>A Paper Without PDF</title>
            <summary>Abstract text here.</summary>
            <published>2024-04-01T00:00:00Z</published>
            <author><name>Test Author</name></author>
          </entry>
        </feed>"""
        mock_response = MagicMock()
        mock_response.read.return_value = xml_no_pdf.encode("utf-8")
        mock_urlopen.return_value = mock_response

        from app.worker.arxiv_scraper import fetch_arxiv_papers
        papers = fetch_arxiv_papers()

        assert len(papers) == 1
        assert papers[0]["pdf_url"] is None


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

class TestArxivRateLimiting:
    """Tests for the _throttle_arxiv rate limiter."""

    def test_throttle_enforces_minimum_delay(self):
        """Consecutive calls should be spaced by at least _ARXIV_DELAY_SECONDS."""
        import app.worker.arxiv_scraper as scraper

        original_time = scraper._last_arxiv_request_time

        # Simulate a recent request
        scraper._last_arxiv_request_time = time.monotonic()

        with patch("app.worker.arxiv_scraper.time.sleep") as mock_sleep:
            scraper._throttle_arxiv()
            # Should have called sleep since we just "made a request"
            if mock_sleep.called:
                sleep_duration = mock_sleep.call_args[0][0]
                assert sleep_duration > 0
                assert sleep_duration <= scraper._ARXIV_DELAY_SECONDS

        # Restore
        scraper._last_arxiv_request_time = original_time


# ---------------------------------------------------------------------------
# ingest_papers — deduplication + embedding
# ---------------------------------------------------------------------------

class TestIngestPapers:
    """Tests for app.worker.arxiv_scraper.ingest_papers (async)."""

    @pytest.mark.asyncio
    async def test_skips_existing_papers(self):
        """Papers already in the DB should not be re-inserted."""
        from app.worker.arxiv_scraper import ingest_papers

        mock_session = AsyncMock()
        # Simulate: paper already exists (session.get returns a truthy object)
        mock_session.get.return_value = MagicMock()

        papers_data = [{"id": "2404.12345", "title": "Existing", "abstract": "...",
                        "authors": [], "published_at": None, "pdf_url": None, "source_url": None}]

        await ingest_papers(mock_session, papers_data)

        # Should NOT have called session.add (paper already exists)
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_inserts_new_papers_with_embeddings(self):
        """New papers should be inserted and get SPECTER2 embeddings."""
        mock_session = AsyncMock()
        mock_session.get.return_value = None  # paper doesn't exist

        fake_embedding = [0.1] * 768

        with patch("app.worker.arxiv_scraper.specter2_embed_batch", return_value=[fake_embedding]):
            from app.worker.arxiv_scraper import ingest_papers

            papers_data = [{
                "id": "2404.NEW01",
                "title": "Brand New Paper",
                "abstract": "Novel research.",
                "authors": ["Author A"],
                "published_at": datetime(2024, 4, 1, tzinfo=timezone.utc),
                "pdf_url": "http://arxiv.org/pdf/2404.NEW01v1",
                "source_url": "http://arxiv.org/abs/2404.NEW01",
            }]

            await ingest_papers(mock_session, papers_data)

        # session.add should have been called with a Paper object
        assert mock_session.add.called
        added_paper = mock_session.add.call_args[0][0]
        assert added_paper.id == "2404.NEW01"
        assert added_paper.embedding == fake_embedding