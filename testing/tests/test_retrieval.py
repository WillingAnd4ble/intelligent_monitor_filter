"""
Tests for the hybrid RRF retrieval system.

Since PostgreSQL pgvector + tsvector cannot run in SQLite, these tests
verify the *logic* of RRF scoring and the query contract by mocking the
database layer.  A separate integration test (against real Postgres)
would complement these if the Docker DB is available.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


# ---------------------------------------------------------------------------
# RRF score formula — pure math, no DB
# ---------------------------------------------------------------------------

class TestRRFScoreFormula:
    """Verify the Reciprocal Rank Fusion formula in isolation."""

    @staticmethod
    def rrf_score(rank_semantic: int, rank_lexical: int, k: int = 60) -> float:
        """Mirror the SQL formula: 1/(k+rank_s) + 1/(k+rank_l)"""
        sem = 1.0 / (k + rank_semantic) if rank_semantic else 0.0
        lex = 1.0 / (k + rank_lexical) if rank_lexical else 0.0
        return sem + lex

    def test_paper_matching_both_legs_scores_highest(self):
        """A paper ranked #1 in both semantic and lexical should beat all others."""
        both = self.rrf_score(1, 1)
        sem_only = self.rrf_score(1, None)
        lex_only = self.rrf_score(None, 1)
        assert both > sem_only
        assert both > lex_only

    def test_equal_weights_for_symmetric_ranks(self):
        """RRF with identical ranks from both legs should be symmetric."""
        score_a = self.rrf_score(5, 10)
        score_b = self.rrf_score(10, 5)
        assert abs(score_a - score_b) < 1e-10

    def test_higher_rank_means_lower_score(self):
        """Rank 1 should score higher than rank 50."""
        better = self.rrf_score(1, 1)
        worse = self.rrf_score(50, 50)
        assert better > worse

    def test_k_parameter_dampens_outliers(self):
        """With a larger k, the difference between rank 1 and rank 2 shrinks."""
        diff_k10 = self.rrf_score(1, 1, k=10) - self.rrf_score(2, 2, k=10)
        diff_k100 = self.rrf_score(1, 1, k=100) - self.rrf_score(2, 2, k=100)
        assert diff_k10 > diff_k100, "Larger k should dampen rank differences"

    def test_single_leg_match_still_gets_score(self):
        """A paper matching only one search leg should still have a positive score."""
        sem_only = self.rrf_score(3, None)
        lex_only = self.rrf_score(None, 3)
        assert sem_only > 0
        assert lex_only > 0


# ---------------------------------------------------------------------------
# perform_hybrid_rrf_search — query contract
# ---------------------------------------------------------------------------
#
# After the ts_rank_cd -> rank_bm25 migration, perform_hybrid_rrf_search runs
# TWO separate SQL executions per call:
#   1. semantic CTE: pgvector cosine, top-N
#   2. lexical filter: tsvector @@ tsquery boolean filter
# BM25 scoring + RRF fusion happen in Python. Mocks below mirror that with
# `side_effect=[sem_result, lex_result]` so the first await returns the
# semantic-side rows, the second returns the lexical-side rows.

def _mock_result(rows):
    """Build a result-proxy mock whose .mappings().fetchall() returns `rows`."""
    rp = MagicMock()
    rp.mappings.return_value.fetchall.return_value = rows
    return rp


class TestHybridRRFSearch:
    """Tests for app.db.retrieval.perform_hybrid_rrf_search."""

    @pytest.mark.asyncio
    async def test_returns_list_of_dicts(self):
        """Returns list of dicts with id, title, abstract, rrf_score; sorted by RRF score desc."""
        mock_session = AsyncMock()

        # Paper A appears in both legs -> highest RRF score.
        # Paper B appears in semantic only -> lower score.
        sem_row_a = {
            "id": "2404.12345", "title": "Multi-agent paper",
            "abstract": "We propose multi-agent coordination via LLMs.",
            "authors": '["Auth1"]', "pdf_url": "http://...", "source_url": "http://...",
            "published_at": None,
        }
        sem_row_b = {
            "id": "2404.67890", "title": "Quantum bounds",
            "abstract": "Entanglement bounds in lattice systems.",
            "authors": '["Auth2"]', "pdf_url": None, "source_url": "http://...",
            "published_at": None,
        }
        lex_row_a = sem_row_a  # A also matches the lexical filter

        mock_session.execute = AsyncMock(side_effect=[
            _mock_result([sem_row_a, sem_row_b]),  # semantic leg
            _mock_result([lex_row_a]),              # lexical leg (only A)
        ])

        from app.db.retrieval import perform_hybrid_rrf_search
        results = await perform_hybrid_rrf_search(
            session=mock_session,
            query_text="multi-agent systems",
            query_embedding=[0.0] * 768,
            limit=10,
        )

        assert isinstance(results, list)
        assert len(results) == 2
        # A appears in both legs -> wins
        assert results[0]["id"] == "2404.12345"
        assert results[0]["rrf_score"] > results[1]["rrf_score"]
        # rrf_score now computed in Python (not returned by SQL); must be present
        assert all("rrf_score" in r for r in results)

    @pytest.mark.asyncio
    async def test_passes_embedding_as_vector_string(self):
        """The embedding must reach the SEMANTIC leg as a pgvector-compatible string."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=[
            _mock_result([]),  # semantic
            _mock_result([]),  # lexical
        ])

        from app.db.retrieval import perform_hybrid_rrf_search
        test_embedding = [0.5, -0.3, 0.1]  # short for testing
        await perform_hybrid_rrf_search(
            session=mock_session,
            query_text="test",
            query_embedding=test_embedding,
            limit=5,
        )

        # The FIRST execute call is the semantic leg — that's where the
        # embedding bind param lives. (Lexical leg only takes :query_text.)
        first_call_params = mock_session.execute.call_args_list[0][0][1]
        assert first_call_params["embedding_val"] == "[0.5,-0.3,0.1]"

    @pytest.mark.asyncio
    async def test_respects_limit_parameter(self):
        """LIMIT is bound on the semantic SQL and final output is capped at `limit`."""
        mock_session = AsyncMock()
        # Return 5 semantic rows; with limit=2 final output must trim to 2.
        sem_rows = [
            {"id": f"p{i}", "title": f"T{i}", "abstract": f"A{i}",
             "authors": "[]", "pdf_url": None, "source_url": None, "published_at": None}
            for i in range(5)
        ]
        mock_session.execute = AsyncMock(side_effect=[
            _mock_result(sem_rows),
            _mock_result([]),  # no lexical match
        ])

        from app.db.retrieval import perform_hybrid_rrf_search
        results = await perform_hybrid_rrf_search(
            session=mock_session,
            query_text="test",
            query_embedding=[0.0] * 768,
            limit=2,
        )

        # Semantic execute must have received the limit
        sem_call_params = mock_session.execute.call_args_list[0][0][1]
        assert sem_call_params["limit"] == 2
        # And final output is trimmed to the same cap
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_returns_empty_on_no_matches(self):
        """When neither leg returns rows, the function returns an empty list."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=[
            _mock_result([]),  # semantic empty
            _mock_result([]),  # lexical empty
        ])

        from app.db.retrieval import perform_hybrid_rrf_search
        results = await perform_hybrid_rrf_search(
            session=mock_session,
            query_text="completely unrelated query xyz",
            query_embedding=[0.0] * 768,
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_bm25_assigns_lexical_ranks(self):
        """A lexical-only candidate (no semantic match) must still get a
        non-zero rrf_score, which proves BM25 actually ran in the lexical leg.

        We avoid asserting a specific BM25 ordering here on purpose — with a
        corpus this small, BM25's IDF term goes negative for any query token
        present in every document (log((N-df+0.5)/(df+0.5)) < 0 when df is
        close to N), which can invert intuitive rankings. The integration
        tests at tests/test_retrieval_integration.py exercise BM25 ordering
        with a real PostgreSQL corpus that doesn't have this degeneracy.

        What this unit test does check: with one lexical-only paper, lexical
        rank is 1 by enumeration, semantic_ranks is empty, so the final
        rrf_score must equal exactly 1/(rrf_k_lexical + 1) = 1/61 ≈ 0.01639.
        If BM25 (or the ranking loop) were skipped, the lexical rank dict
        would stay empty and rrf_score would be 0.
        """
        mock_session = AsyncMock()
        lex_paper = {
            "id": "lex_only", "title": "Multi-agent coordination",
            "abstract": "Cooperating agents collaborate via natural language.",
            "authors": "[]", "pdf_url": None, "source_url": None, "published_at": None,
        }
        mock_session.execute = AsyncMock(side_effect=[
            _mock_result([]),            # semantic empty -> no semantic_rank
            _mock_result([lex_paper]),   # one lexical-only candidate
        ])

        from app.db.retrieval import perform_hybrid_rrf_search
        results = await perform_hybrid_rrf_search(
            session=mock_session,
            query_text="agent",
            query_embedding=[0.0] * 768,
            limit=10,
            rrf_k_lexical=60,  # explicit so the assertion below is unambiguous
        )

        assert len(results) == 1
        assert results[0]["id"] == "lex_only"
        # Rank 1 in lexical, no semantic contribution -> RRF score must be 1/61.
        assert results[0]["rrf_score"] == pytest.approx(1.0 / 61, rel=1e-9), (
            "BM25 must assign the lexical-only candidate rank 1, yielding "
            f"rrf_score = 1/(60+1); got {results[0]['rrf_score']}"
        )


# ---------------------------------------------------------------------------
# SPECTER2 embedding contract
# ---------------------------------------------------------------------------

class TestSpecter2Embedding:
    """Tests for the SPECTER2 embedding wrapper (modal_client)."""

    @pytest.mark.asyncio
    async def test_mock_embeddings_return_768_dimensions(self):
        """When Modal is disabled, mock embeddings should still be 768-dim."""
        with patch("app.worker.modal_client.settings") as mock_settings:
            mock_settings.MODAL_GPU_ENABLED = False
            mock_settings.MODAL_TOKEN_ID = None
            mock_settings.MODAL_TOKEN_SECRET = None

            from app.worker.modal_client import specter2_embed_batch
            pairs = [
                {"title": "Paper A", "abstract": "About LLMs"},
                {"title": "Paper B", "abstract": "About graphs"},
            ]
            embeddings = await specter2_embed_batch(pairs)

        assert len(embeddings) == 2
        assert len(embeddings[0]) == 768
        assert len(embeddings[1]) == 768
        assert all(isinstance(v, float) for v in embeddings[0])

    @pytest.mark.asyncio
    async def test_mock_embeddings_are_different_per_paper(self):
        """Mock embeddings should not all be identical (they're random)."""
        with patch("app.worker.modal_client.settings") as mock_settings:
            mock_settings.MODAL_GPU_ENABLED = False
            mock_settings.MODAL_TOKEN_ID = None
            mock_settings.MODAL_TOKEN_SECRET = None

            from app.worker.modal_client import specter2_embed_batch
            pairs = [
                {"title": "Paper A", "abstract": "About LLMs"},
                {"title": "Paper B", "abstract": "About graphs"},
            ]
            embeddings = await specter2_embed_batch(pairs)

        # Extremely unlikely for two random vectors to be identical
        assert embeddings[0] != embeddings[1]

    @pytest.mark.asyncio
    async def test_embed_batch_formats_title_sep_abstract(self):
        """The text sent to SPECTER2 should be 'title [SEP] abstract'."""
        from unittest.mock import AsyncMock

        mock_embedder = MagicMock()
        mock_embedder.embed_batch.remote.aio = AsyncMock(return_value=[[0.0] * 768])

        mock_cls = MagicMock(return_value=mock_embedder)
        mock_modal = MagicMock()
        mock_modal.Cls.from_name.return_value = mock_cls

        with patch("app.worker.modal_client.settings") as mock_settings:
            mock_settings.MODAL_GPU_ENABLED = True
            mock_settings.MODAL_TOKEN_ID = "fake"
            mock_settings.MODAL_TOKEN_SECRET = "fake"

            import builtins
            real_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == "modal":
                    return mock_modal
                return real_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                from app.worker.modal_client import specter2_embed_batch
                await specter2_embed_batch([{"title": "My Title", "abstract": "My Abstract"}])

        sent_texts = mock_embedder.embed_batch.remote.aio.call_args[0][0]
        assert sent_texts[0] == "My Title [SEP] My Abstract"