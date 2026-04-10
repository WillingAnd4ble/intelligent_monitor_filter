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

class TestHybridRRFSearch:
    """Tests for app.db.retrieval.perform_hybrid_rrf_search."""

    @pytest.mark.asyncio
    async def test_returns_list_of_dicts(self):
        """The function must return a list of dicts, each with id, title, abstract."""
        mock_session = AsyncMock()

        # Simulate DB returning 2 rows as mappings
        mock_row_1 = {
            "id": "2404.12345", "title": "Paper A", "abstract": "Abstract A",
            "authors": '["Auth1"]', "pdf_url": "http://...", "source_url": "http://...",
            "published_at": None, "rrf_score": 0.033,
        }
        mock_row_2 = {
            "id": "2404.67890", "title": "Paper B", "abstract": "Abstract B",
            "authors": '["Auth2"]', "pdf_url": None, "source_url": "http://...",
            "published_at": None, "rrf_score": 0.020,
        }

        mock_result = MagicMock()
        mock_result.mappings.return_value.fetchall.return_value = [mock_row_1, mock_row_2]
        mock_session.execute.return_value = mock_result

        from app.db.retrieval import perform_hybrid_rrf_search
        results = await perform_hybrid_rrf_search(
            session=mock_session,
            query_text="multi-agent systems",
            query_embedding=[0.0] * 768,
            limit=10,
        )

        assert isinstance(results, list)
        assert len(results) == 2
        assert results[0]["id"] == "2404.12345"
        assert results[0]["rrf_score"] > results[1]["rrf_score"]

    @pytest.mark.asyncio
    async def test_passes_embedding_as_vector_string(self):
        """The embedding must be formatted as a pgvector-compatible string '[0.1,0.2,...]'."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        from app.db.retrieval import perform_hybrid_rrf_search
        test_embedding = [0.5, -0.3, 0.1]  # short for testing
        await perform_hybrid_rrf_search(
            session=mock_session,
            query_text="test",
            query_embedding=test_embedding,
            limit=5,
        )

        # Check that execute was called and the embedding param is a vector string
        call_args = mock_session.execute.call_args
        params = call_args[0][1]  # second positional arg = bind params
        assert params["embedding_val"] == "[0.5,-0.3,0.1]"

    @pytest.mark.asyncio
    async def test_respects_limit_parameter(self):
        """The LIMIT in the query should match what was passed in."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        from app.db.retrieval import perform_hybrid_rrf_search
        await perform_hybrid_rrf_search(
            session=mock_session,
            query_text="test",
            query_embedding=[0.0] * 768,
            limit=25,
        )

        call_args = mock_session.execute.call_args
        params = call_args[0][1]
        assert params["limit"] == 25

    @pytest.mark.asyncio
    async def test_returns_empty_on_no_matches(self):
        """When neither search leg finds anything, return an empty list."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        from app.db.retrieval import perform_hybrid_rrf_search
        results = await perform_hybrid_rrf_search(
            session=mock_session,
            query_text="completely unrelated query xyz",
            query_embedding=[0.0] * 768,
        )

        assert results == []


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