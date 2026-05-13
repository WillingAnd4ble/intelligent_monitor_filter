"""
Shared fixtures for the entire test suite.

Strategy:
  - Agent/scraper tests:  pure unit tests, mock all LLM & HTTP calls.
  - Retrieval tests:      mock the raw SQL since SQLite can't run pgvector/tsvector.
  - API tests:            FastAPI TestClient with dependency overrides.
"""

import sys
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

import pytest

# ---------------------------------------------------------------------------
# Make the backend package importable from the testing directory
# ---------------------------------------------------------------------------
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# ---------------------------------------------------------------------------
# Prevent Settings from requiring a real .env at import time
# ---------------------------------------------------------------------------
os.environ.setdefault("JWT_SECRET", "test-secret-key-not-for-production")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5433/test_db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key")
os.environ.setdefault("MODAL_GPU_ENABLED", "False")

# ---------------------------------------------------------------------------
# Stub out the async DB engine before any backend module imports it.
# The backend's database.py calls create_async_engine at module scope,
# which tries to import asyncpg — not installed in the test env.
# ---------------------------------------------------------------------------
from unittest.mock import MagicMock as _MagicMock
import sqlalchemy.ext.asyncio as _async_sa
_orig_create = _async_sa.create_async_engine
_async_sa.create_async_engine = _MagicMock(name="mock_create_async_engine")


# ===== SAMPLE DATA FIXTURES ================================================

SAMPLE_USER_ID = str(uuid.uuid4())

SAMPLE_PAPER = {
    "id": "2404.12345",
    "title": "Multi-Agent Coordination via Large Language Models",
    "abstract": (
        "We propose a framework where multiple LLM-based agents coordinate "
        "through natural language to solve complex planning tasks. Our approach "
        "uses a shared communication protocol and achieves state-of-the-art "
        "results on collaborative benchmarks."
    ),
    "authors": ["Alice Smith", "Bob Jones"],
    "published_at": datetime(2024, 4, 15, tzinfo=timezone.utc),
    "pdf_url": "http://arxiv.org/pdf/2404.12345v1",
    "source_url": "http://arxiv.org/abs/2404.12345",
}

SAMPLE_PAPER_IRRELEVANT = {
    "id": "2404.99999",
    "title": "Optimal Crop Rotation Strategies in Scandinavian Agriculture",
    "abstract": (
        "This paper reviews crop rotation methods for Nordic climates, "
        "analyzing soil nitrogen retention and yield variance over 20-year "
        "field trials in Sweden and Norway."
    ),
    "authors": ["Carl Svensson"],
    "published_at": datetime(2024, 4, 10, tzinfo=timezone.utc),
    "pdf_url": "http://arxiv.org/pdf/2404.99999v1",
    "source_url": "http://arxiv.org/abs/2404.99999",
}

SAMPLE_DISTILLED_CRITERIA = [
    "Must feature multi-agent systems with 2 or more collaborating agents",
    "Must focus on Large Language Models (not classical robotics or RL-only)",
    "Must include experimental evaluation or benchmarks",
    "Must discuss inter-agent communication or coordination mechanisms",
]

SAMPLE_FEEDBACK_MEMORY = (
    "User dislikes papers focused on single-agent reinforcement learning, "
    "pure robotics control, and theoretical proofs without experiments."
)


# ===== ARXIV XML FIXTURE ===================================================

SAMPLE_ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2404.12345</id>
    <title>Multi-Agent Coordination via Large Language Models</title>
    <summary>We propose a framework where multiple LLM-based agents coordinate through natural language to solve complex planning tasks.</summary>
    <published>2024-04-15T00:00:00Z</published>
    <author><name>Alice Smith</name></author>
    <author><name>Bob Jones</name></author>
    <link title="pdf" href="http://arxiv.org/pdf/2404.12345v1" rel="related" type="application/pdf"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2404.67890</id>
    <title>Attention Mechanisms for Graph Neural Networks</title>
    <summary>We study how attention can be applied to GNNs for molecular property prediction tasks.</summary>
    <published>2024-04-14T00:00:00Z</published>
    <author><name>Charlie Brown</name></author>
    <link title="pdf" href="http://arxiv.org/pdf/2404.67890v1" rel="related" type="application/pdf"/>
  </entry>
</feed>"""


# ===== AGENT STATE FACTORY ==================================================

@pytest.fixture
def make_agent_state():
    """Factory fixture: returns a function that builds an AgentState dict."""
    def _make(
        paper=None,
        criteria=None,
        feedback_memory="",
        content_interest=None,
    ):
        p = paper or SAMPLE_PAPER
        return {
            "user_id": SAMPLE_USER_ID,
            "user_intent": "Find papers on multi-agent LLM systems",
            "distilled_criteria": criteria or SAMPLE_DISTILLED_CRITERIA,
            "content_interest": content_interest or ["methodology", "experiments"],
            "feedback_memory": feedback_memory,
            "current_paper_id": p["id"],
            "raw_abstract": p["abstract"],
            "pdf_url": p.get("pdf_url"),
            "extracted_pdf_text": None,
            "sectioned_text": None,
            "evaluator_decision": "borderline",
            "evaluator_reasonbook": "",
            "critique_decision": True,
            "critique_reasonbook": "",
            "final_explanation": "",
            "agent_score": 0.0,
        }
    return _make


# ===== LLM MOCK HELPERS ====================================================

def make_mock_structured_output(return_value):
    """
    Creates a mock ChatOpenAI whose .with_structured_output() works with
    LangChain's pipe operator: (prompt | structured).invoke({...}) -> return_value.

    The trick: with_structured_output returns a Runnable-like object.
    LangChain's prompt.__or__(runnable) builds a RunnableSequence whose
    .invoke() eventually calls runnable.invoke().  So we need the mock
    structured object to have a working .invoke() method.
    """
    mock_chain_result = MagicMock()
    mock_chain_result.invoke.return_value = return_value

    # Make something that acts like a LangChain Runnable
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = return_value
    # Support batch/abatch/stream too in case they're called
    mock_structured.batch.return_value = [return_value]

    # For the pipe operator: prompt | mock_structured
    # LangChain calls prompt.__or__(mock_structured), which checks if the
    # right side has InputType/OutputType. If not, it tries to wrap it.
    # Easiest: make it also support __ror__ so prompt | structured works
    mock_structured.__or__ = MagicMock(return_value=mock_chain_result)
    mock_structured.__ror__ = MagicMock(return_value=mock_chain_result)

    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured

    return mock_llm, mock_chain_result


# ===== NEW FIXTURES FOR PIPELINE/AUTH TESTS =================================

@pytest.fixture
def eager_celery():
    """Run Celery tasks in-process so `.delay()` / `.apply_async()` execute immediately."""
    from app.worker.celery_app import celery_app
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield celery_app
    celery_app.conf.task_always_eager = False
    celery_app.conf.task_eager_propagates = False


@pytest.fixture
def mock_specter2_modal():
    """Patch the SPECTER2 Modal call to return deterministic 768-d vectors."""
    import hashlib
    def _fake(title_abstract_pairs):
        out = []
        for pair in title_abstract_pairs:
            seed = int(hashlib.md5(
                (pair["title"] + pair["abstract"]).encode("utf-8")
            ).hexdigest(), 16) % (2**32)
            import random
            r = random.Random(seed)
            out.append([r.random() for _ in range(768)])
        return out

    with patch("app.worker.modal_client.specter2_embed_batch", new=AsyncMock(side_effect=_fake)) as m:
        yield m


@pytest.fixture
def mock_marker_modal():
    """Patch Marker to return a short canned markdown."""
    canned = "# Stub paper\n\nThis is a canned Marker output used in tests.\n"
    with patch("app.worker.modal_client.marker_extract_pdf", new=AsyncMock(return_value=canned)) as m:
        yield m


@pytest.fixture
def test_user_cookie():
    """Generate a valid JWT cookie for a test user UUID."""
    import uuid
    from app.core.security import create_access_token
    uid = uuid.uuid4()
    return {
        "user_id": uid,
        "cookie": {"access_token": create_access_token(uid)},
    }


@pytest.fixture
def seeded_papers():
    """Deterministic small set of arXiv paper dicts."""
    return [
        {
            "id": "2605.01100",
            "title": "Multi-Agent Reinforcement Learning at Scale",
            "abstract": "We study coordination across LLM-driven agents in long-horizon tasks.",
            "authors": ["A. One"],
            "published_at": datetime(2026, 5, 12, tzinfo=timezone.utc),
            "pdf_url": "http://arxiv.org/pdf/2605.01100v1",
            "source_url": "http://arxiv.org/abs/2605.01100",
        },
        {
            "id": "2605.01101",
            "title": "Crop Rotation Yield Models",
            "abstract": "Twenty-year field trial review of crop rotation in Scandinavia.",
            "authors": ["B. Two"],
            "published_at": datetime(2026, 5, 12, tzinfo=timezone.utc),
            "pdf_url": "http://arxiv.org/pdf/2605.01101v1",
            "source_url": "http://arxiv.org/abs/2605.01101",
        },
    ]