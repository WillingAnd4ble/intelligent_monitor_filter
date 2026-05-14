"""
Unit tests for the agent layer.

Covers the components that exist in the current cascade architecture:
GoalDistiller, the Phase 1 graph nodes (evaluator, critique) and the
section-classifier helper used by the library deep-explanation chain.

NOTE ON SCOPE: an earlier pre-cascade architecture had separate LangGraph
nodes for PDF extraction, section classification, explanation and ranking,
each with its own unit tests. When the pipeline was redesigned into the
Phase 1 + run_deep_reader() cascade, those nodes were removed and the tests
that targeted them were deleted along with the architecture they verified.
This file now tracks only the live agent surface.

Mocking strategy: we patch ChatOpenAI at the point of import so that the
entire prompt | structured chain returns a fake Pydantic output.
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
    """run_goal_distiller returns a DistilledCriteriaOutput carrying both the
    boolean criteria list and the BM25 lexical_query."""

    def test_returns_distilled_criteria_output(self):
        from app.agents.distiller import DistilledCriteriaOutput

        fake_output = DistilledCriteriaOutput(
            distilled_criteria=[
                "Must feature multi-agent systems",
                "Must focus on LLMs",
                "Must include experiments",
            ],
            lexical_query="multi-agent LLM coordination",
        )
        patcher, mock_chain = _patch_llm_chain("app.agents.distiller.ChatOpenAI", fake_output)

        with patcher:
            from app.agents.distiller import run_goal_distiller
            result = run_goal_distiller(
                categories=["cs.AI"],
                topics=["multi-agent"],
                content_interest=["methodology"],
                filtering_goal="Find papers on multi-agent LLM coordination",
            )

        assert isinstance(result, DistilledCriteriaOutput)
        assert len(result.distilled_criteria) == 3
        assert "multi-agent" in result.distilled_criteria[0].lower()
        assert result.lexical_query == "multi-agent LLM coordination"

    def test_returns_empty_when_no_goal_or_interest(self):
        from app.agents.distiller import run_goal_distiller

        result = run_goal_distiller(
            categories=["cs.AI"], topics=[], content_interest=[], filtering_goal=""
        )
        assert result.distilled_criteria == []
        assert result.lexical_query == ""

    def test_criteria_count_within_bounds(self):
        from app.agents.distiller import DistilledCriteriaOutput

        fake_output = DistilledCriteriaOutput(
            distilled_criteria=["C1", "C2", "C3", "C4", "C5"],
            lexical_query="agent systems benchmark",
        )
        patcher, _ = _patch_llm_chain("app.agents.distiller.ChatOpenAI", fake_output)

        with patcher:
            from app.agents.distiller import run_goal_distiller
            result = run_goal_distiller(
                categories=["cs.AI"], topics=["agents"],
                content_interest=["experiments"], filtering_goal="Agent systems",
            )
        assert 3 <= len(result.distilled_criteria) <= 7


# ===================================================================
# EVALUATOR NODE
# ===================================================================

class TestEvaluatorNode:

    def test_accept_decision(self, make_agent_state):
        from app.agents.schemas import EvaluatorOutput

        fake = EvaluatorOutput(decision="accept", score=8.0, reasonbook="Matches multi-agent LLM criteria.", user_explanation="Stub explanation for tests.")
        patcher, _ = _patch_llm_chain("app.agents.graph.ChatOpenAI", fake)

        with patcher:
            from app.agents.graph import node_evaluator
            result = node_evaluator(make_agent_state(paper=SAMPLE_PAPER))

        assert result["evaluator_decision"] == "accept"

    def test_reject_decision(self, make_agent_state):
        from app.agents.schemas import EvaluatorOutput

        fake = EvaluatorOutput(decision="reject", score=1.5, reasonbook="About agriculture.", user_explanation="Stub explanation for tests.")
        patcher, _ = _patch_llm_chain("app.agents.graph.ChatOpenAI", fake)

        with patcher:
            from app.agents.graph import node_evaluator
            result = node_evaluator(make_agent_state(paper=SAMPLE_PAPER_IRRELEVANT))

        assert result["evaluator_decision"] == "reject"

    def test_borderline_decision(self, make_agent_state):
        from app.agents.schemas import EvaluatorOutput

        fake = EvaluatorOutput(decision="borderline", score=5.0, reasonbook="Mentions agents but mostly RL.", user_explanation="Stub explanation for tests.")
        patcher, _ = _patch_llm_chain("app.agents.graph.ChatOpenAI", fake)

        with patcher:
            from app.agents.graph import node_evaluator
            result = node_evaluator(make_agent_state())

        assert result["evaluator_decision"] == "borderline"

    def test_evaluator_returns_user_explanation(self, make_agent_state):
        from app.agents.schemas import EvaluatorOutput

        fake_output = EvaluatorOutput(
            decision="accept",
            score=8.5,
            reasonbook="Internal: paper covers multi-agent coordination per criterion 1.",
            user_explanation="This paper proposes a multi-agent coordination framework, "
                             "matching your interest in LLM-based agentic systems.",
        )
        patcher, _ = _patch_llm_chain("app.agents.graph.ChatOpenAI", fake_output)

        with patcher:
            from app.agents.graph import node_evaluator
            state = make_agent_state()
            result = node_evaluator(state)

        assert "evaluator_user_explanation" in result
        assert "multi-agent coordination framework" in result["evaluator_user_explanation"]

    def test_evaluator_uses_criteria_in_prompt(self, make_agent_state):
        from app.agents.schemas import EvaluatorOutput

        fake = EvaluatorOutput(decision="accept", score=8.0, reasonbook="ok", user_explanation="Stub explanation for tests.")
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
# SECTION CLASSIFIER (library deep-explanation helper)
# ===================================================================

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
