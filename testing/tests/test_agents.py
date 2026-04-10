"""
Unit tests for every agent node in the LangGraph pipeline.

Each node is tested in isolation: the LLM is mocked so we only verify
that the node reads the right state fields and writes the correct output keys.

Mocking strategy: We patch ChatOpenAI at the point of import (app.agents.graph)
so that the entire prompt|structured chain returns our fake Pydantic output.
"""

from unittest.mock import patch, MagicMock, PropertyMock
import pytest

from conftest import (
    SAMPLE_PAPER,
    SAMPLE_PAPER_IRRELEVANT,
    SAMPLE_DISTILLED_CRITERIA,
    SAMPLE_FEEDBACK_MEMORY,
)


def _patch_llm_chain(module_path, return_value):
    """
    Return a patch context manager that makes any
    (ChatPromptTemplate | llm.with_structured_output()).invoke(...)
    return `return_value`.

    Strategy: We return a real-ish LLM mock whose .with_structured_output()
    returns a FakeRunnable. LangChain's prompt | FakeRunnable creates a
    RunnableSequence where FakeRunnable.invoke() is the final step.
    """
    from langchain_core.runnables import RunnableLambda

    # Track what invoke was called with
    _invoke_tracker = MagicMock()
    _invoke_tracker.invoke.return_value = return_value

    def _fake_invoke(input_val, config=None, **kwargs):
        _invoke_tracker.invoke(input_val)
        return return_value

    fake_runnable = RunnableLambda(_fake_invoke)

    mock_llm_instance = MagicMock()
    mock_llm_instance.with_structured_output.return_value = fake_runnable

    return patch(module_path, return_value=mock_llm_instance), _invoke_tracker


# ===================================================================
# GOAL DISTILLER
# ===================================================================

class TestGoalDistiller:

    def test_returns_list_of_criteria(self):
        from app.agents.distiller import DistilledCriteriaOutput

        fake_output = DistilledCriteriaOutput(distilled_criteria=[
            "Must feature multi-agent systems",
            "Must focus on LLMs",
            "Must include experiments",
        ])
        patcher, mock_chain = _patch_llm_chain("app.agents.distiller.ChatOpenAI", fake_output)

        with patcher:
            from app.agents.distiller import run_goal_distiller
            result = run_goal_distiller(
                categories=["cs.AI"],
                topics=["multi-agent"],
                content_interest=["methodology"],
                filtering_goal="Find papers on multi-agent LLM coordination",
            )

        assert isinstance(result, list)
        assert len(result) == 3
        assert "multi-agent" in result[0].lower()

    def test_returns_empty_when_no_goal_or_interest(self):
        from app.agents.distiller import run_goal_distiller

        result = run_goal_distiller(
            categories=["cs.AI"], topics=[], content_interest=[], filtering_goal=""
        )
        assert result == []

    def test_criteria_count_within_bounds(self):
        from app.agents.distiller import DistilledCriteriaOutput

        fake_output = DistilledCriteriaOutput(
            distilled_criteria=["C1", "C2", "C3", "C4", "C5"]
        )
        patcher, _ = _patch_llm_chain("app.agents.distiller.ChatOpenAI", fake_output)

        with patcher:
            from app.agents.distiller import run_goal_distiller
            result = run_goal_distiller(
                categories=["cs.AI"], topics=["agents"],
                content_interest=["experiments"], filtering_goal="Agent systems",
            )
        assert 3 <= len(result) <= 7


# ===================================================================
# EVALUATOR NODE
# ===================================================================

class TestEvaluatorNode:

    def test_accept_decision(self, make_agent_state):
        from app.agents.schemas import EvaluatorOutput

        fake = EvaluatorOutput(decision="accept", reasonbook="Matches multi-agent LLM criteria.")
        patcher, _ = _patch_llm_chain("app.agents.graph.ChatOpenAI", fake)

        with patcher:
            from app.agents.graph import node_evaluator
            result = node_evaluator(make_agent_state(paper=SAMPLE_PAPER))

        assert result["evaluator_decision"] == "accept"

    def test_reject_decision(self, make_agent_state):
        from app.agents.schemas import EvaluatorOutput

        fake = EvaluatorOutput(decision="reject", reasonbook="About agriculture.")
        patcher, _ = _patch_llm_chain("app.agents.graph.ChatOpenAI", fake)

        with patcher:
            from app.agents.graph import node_evaluator
            result = node_evaluator(make_agent_state(paper=SAMPLE_PAPER_IRRELEVANT))

        assert result["evaluator_decision"] == "reject"

    def test_borderline_decision(self, make_agent_state):
        from app.agents.schemas import EvaluatorOutput

        fake = EvaluatorOutput(decision="borderline", reasonbook="Mentions agents but mostly RL.")
        patcher, _ = _patch_llm_chain("app.agents.graph.ChatOpenAI", fake)

        with patcher:
            from app.agents.graph import node_evaluator
            result = node_evaluator(make_agent_state())

        assert result["evaluator_decision"] == "borderline"

    def test_evaluator_uses_criteria_in_prompt(self, make_agent_state):
        from app.agents.schemas import EvaluatorOutput

        fake = EvaluatorOutput(decision="accept", reasonbook="ok")
        patcher, mock_chain = _patch_llm_chain("app.agents.graph.ChatOpenAI", fake)

        custom_criteria = ["Must mention transformers", "Must have code"]
        with patcher:
            from app.agents.graph import node_evaluator
            node_evaluator(make_agent_state(criteria=custom_criteria))

        # The invoke receives a ChatPromptValue — check criteria appear in the rendered prompt
        assert mock_chain.invoke.called
        prompt_value = mock_chain.invoke.call_args[0][0]
        prompt_text = str(prompt_value)
        assert "Must mention transformers" in prompt_text


# ===================================================================
# CRITIQUE NODE
# ===================================================================

class TestCritiqueNode:

    def test_auto_passes_when_no_feedback_memory(self, make_agent_state):
        from app.agents.graph import node_critique

        result = node_critique(make_agent_state(feedback_memory=""))
        assert result["critique_decision"] is True
        assert "Auto-passed" in result["critique_reasonbook"]

    def test_auto_passes_when_whitespace_only_memory(self, make_agent_state):
        from app.agents.graph import node_critique

        result = node_critique(make_agent_state(feedback_memory="   "))
        assert result["critique_decision"] is True

    def test_rejects_when_memory_conflicts(self, make_agent_state):
        from app.agents.schemas import CritiqueOutput

        fake = CritiqueOutput(decision=False, reasonbook="Features single-agent RL user despises.")
        patcher, _ = _patch_llm_chain("app.agents.graph.ChatOpenAI", fake)

        with patcher:
            from app.agents.graph import node_critique
            state = make_agent_state(feedback_memory=SAMPLE_FEEDBACK_MEMORY)
            state["evaluator_reasonbook"] = "Borderline — mentions agents but is mostly RL."
            result = node_critique(state)

        assert result["critique_decision"] is False

    def test_accepts_when_memory_does_not_conflict(self, make_agent_state):
        from app.agents.schemas import CritiqueOutput

        fake = CritiqueOutput(decision=True, reasonbook="No robotics content.")
        patcher, _ = _patch_llm_chain("app.agents.graph.ChatOpenAI", fake)

        with patcher:
            from app.agents.graph import node_critique
            result = node_critique(make_agent_state(feedback_memory=SAMPLE_FEEDBACK_MEMORY))

        assert result["critique_decision"] is True


# ===================================================================
# PDF EXTRACTOR NODE
# ===================================================================

class TestPdfExtractorNode:

    @pytest.mark.asyncio
    async def test_returns_extracted_text_when_pdf_available(self, make_agent_state):
        from unittest.mock import AsyncMock
        with patch("app.worker.modal_client.marker_extract_pdf", new_callable=AsyncMock, return_value="Full PDF text here."):
            from app.agents.graph import node_pdf_extractor
            result = await node_pdf_extractor(make_agent_state())

        assert result["extracted_pdf_text"] == "Full PDF text here."

    @pytest.mark.asyncio
    async def test_falls_back_to_abstract_when_extraction_fails(self, make_agent_state):
        from unittest.mock import AsyncMock
        with patch("app.worker.modal_client.marker_extract_pdf", new_callable=AsyncMock, return_value=""):
            from app.agents.graph import node_pdf_extractor
            state = make_agent_state()
            result = await node_pdf_extractor(state)

        assert result["extracted_pdf_text"] == state["raw_abstract"]

    @pytest.mark.asyncio
    async def test_falls_back_to_abstract_when_no_pdf_url(self, make_agent_state):
        from app.agents.graph import node_pdf_extractor

        state = make_agent_state()
        state["pdf_url"] = None
        result = await node_pdf_extractor(state)

        assert result["extracted_pdf_text"] == state["raw_abstract"]


# ===================================================================
# SECTION CLASSIFIER NODE
# ===================================================================

class TestSectionClassifierNode:

    def test_passthrough_returns_extracted_text(self, make_agent_state):
        """Current graph.py implementation is a passthrough."""
        from app.agents.graph import node_section_classifier

        state = make_agent_state()
        state["extracted_pdf_text"] = "This is the full extracted text."
        result = node_section_classifier(state)

        assert result["sectioned_text"] == "This is the full extracted text."


class TestSectionClassifierLogic:

    def test_short_papers_return_full_text(self):
        from app.agents.section_classifier import classify_sections

        short_text = "\n".join(["Line " + str(i) for i in range(30)])
        result = classify_sections(short_text, ["methodology"])
        assert result == short_text

    def test_empty_content_interest_returns_full_text(self):
        from app.agents.section_classifier import TableOfContents, SectionEntry

        long_text = "\n".join(["Line " + str(i) for i in range(100)])

        fake_toc = TableOfContents(sections=[
            SectionEntry(section_name="1. Introduction", category="introduction",
                         start_line=1, end_line=30),
        ])
        patcher, _ = _patch_llm_chain("app.agents.section_classifier.ChatOpenAI", fake_toc)

        with patcher:
            from app.agents.section_classifier import classify_sections
            result = classify_sections(long_text, [])

        assert result == long_text

    def test_filters_to_matching_sections_only(self):
        from app.agents.section_classifier import TableOfContents, SectionEntry

        lines = ["Line " + str(i) for i in range(100)]
        long_text = "\n".join(lines)

        fake_toc = TableOfContents(sections=[
            SectionEntry(section_name="1. Introduction", category="introduction",
                         start_line=1, end_line=30),
            SectionEntry(section_name="3. Methods", category="methodology",
                         start_line=31, end_line=60),
            SectionEntry(section_name="5. Results", category="experiments",
                         start_line=61, end_line=90),
            SectionEntry(section_name="6. Conclusion", category="conclusions",
                         start_line=91, end_line=100),
        ])
        patcher, _ = _patch_llm_chain("app.agents.section_classifier.ChatOpenAI", fake_toc)

        with patcher:
            from app.agents.section_classifier import classify_sections
            result = classify_sections(long_text, ["methodology", "experiments"])

        assert "## 3. Methods" in result
        assert "## 5. Results" in result
        assert "Introduction" not in result
        assert "Conclusion" not in result

    def test_fallback_when_no_sections_match(self):
        from app.agents.section_classifier import TableOfContents, SectionEntry

        long_text = "\n".join(["Line " + str(i) for i in range(100)])

        fake_toc = TableOfContents(sections=[
            SectionEntry(section_name="1. Introduction", category="introduction",
                         start_line=1, end_line=100),
        ])
        patcher, _ = _patch_llm_chain("app.agents.section_classifier.ChatOpenAI", fake_toc)

        with patcher:
            from app.agents.section_classifier import classify_sections
            result = classify_sections(long_text, ["methodology"])

        assert result == long_text


# ===================================================================
# EXPLAINER NODE
# ===================================================================

class TestExplainerNode:

    def test_returns_explanation_string(self, make_agent_state):
        from app.agents.schemas import ExplainerOutput

        fake = ExplainerOutput(
            explanation="This paper proposes a multi-agent framework. "
                        "It addresses agent communication protocols. "
                        "Results show SOTA performance."
        )
        patcher, _ = _patch_llm_chain("app.agents.graph.ChatOpenAI", fake)

        with patcher:
            from app.agents.graph import node_explainer
            state = make_agent_state()
            state["sectioned_text"] = "Some paper text about agents."
            result = node_explainer(state)

        assert "final_explanation" in result
        assert len(result["final_explanation"]) > 20

    def test_uses_sectioned_text_over_abstract(self, make_agent_state):
        from app.agents.schemas import ExplainerOutput

        fake = ExplainerOutput(explanation="Explanation.")
        patcher, mock_chain = _patch_llm_chain("app.agents.graph.ChatOpenAI", fake)

        with patcher:
            from app.agents.graph import node_explainer
            state = make_agent_state()
            state["sectioned_text"] = "SECTIONED TEXT"
            state["raw_abstract"] = "RAW ABSTRACT"
            node_explainer(state)

        # The rendered prompt should contain the sectioned text, not the abstract
        prompt_value = mock_chain.invoke.call_args[0][0]
        prompt_text = str(prompt_value)
        assert "SECTIONED TEXT" in prompt_text
        assert "RAW ABSTRACT" not in prompt_text


# ===================================================================
# RANKER NODE
# ===================================================================

class TestRankerNode:

    def test_returns_float_score(self, make_agent_state):
        from app.agents.schemas import RankerOutput

        fake = RankerOutput(score=8.5)
        patcher, _ = _patch_llm_chain("app.agents.graph.ChatOpenAI", fake)

        with patcher:
            from app.agents.graph import node_ranker
            state = make_agent_state()
            state["sectioned_text"] = "Multi-agent paper text."
            result = node_ranker(state)

        assert "agent_score" in result
        assert isinstance(result["agent_score"], float)
        assert 0.0 <= result["agent_score"] <= 10.0

    def test_low_score_for_irrelevant(self, make_agent_state):
        from app.agents.schemas import RankerOutput

        fake = RankerOutput(score=2.1)
        patcher, _ = _patch_llm_chain("app.agents.graph.ChatOpenAI", fake)

        with patcher:
            from app.agents.graph import node_ranker
            result = node_ranker(make_agent_state(paper=SAMPLE_PAPER_IRRELEVANT))

        assert result["agent_score"] < 5.0


# ===================================================================
# ROUTING LOGIC
# ===================================================================

class TestRoutingLogic:

    def test_accept_routes_to_pdf_extractor(self):
        from app.agents.graph import route_evaluator_decision
        assert route_evaluator_decision({"evaluator_decision": "accept"}) == "pdf_extractor"

    def test_borderline_routes_to_critique(self):
        from app.agents.graph import route_evaluator_decision
        assert route_evaluator_decision({"evaluator_decision": "borderline"}) == "critique"

    def test_reject_routes_to_end(self):
        from langgraph.graph import END
        from app.agents.graph import route_evaluator_decision
        assert route_evaluator_decision({"evaluator_decision": "reject"}) == END

    def test_critique_true_routes_to_pdf_extractor(self):
        from app.agents.graph import route_critique_decision
        assert route_critique_decision({"critique_decision": True}) == "pdf_extractor"

    def test_critique_false_routes_to_end(self):
        from langgraph.graph import END
        from app.agents.graph import route_critique_decision
        assert route_critique_decision({"critique_decision": False}) == END
