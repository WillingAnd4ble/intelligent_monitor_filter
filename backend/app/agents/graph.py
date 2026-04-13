"""
Phase 1 LangGraph: Evaluator + Critique (abstract-only, no GPU).

Each paper runs through this graph individually (pointwise).
Evaluator scores + decides, Critique reviews borderline cases against feedback_memory.
"""

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.agents.schemas import AgentState, EvaluatorOutput, CritiqueOutput
from app.core.config import settings


def node_evaluator(state: AgentState):
    """Pointwise evaluator: abstract + distilled_criteria → decision + score."""
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.0,
        api_key=settings.OPENAI_API_KEY,
    )
    structured = llm.with_structured_output(EvaluatorOutput)

    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "You are an academic paper screening AI. Evaluate this paper's abstract "
            "against the user's research criteria.\n\n"
            "CRITERIA:\n{criteria}\n\n"
            "INSTRUCTIONS:\n"
            "- Output 'accept' if the paper clearly matches the criteria.\n"
            "- Output 'borderline' if it partially matches or you are uncertain. "
            "When uncertain, PREFER 'borderline' over 'reject'.\n"
            "- Output 'reject' ONLY if the paper clearly does not match.\n"
            "- Assign a relevance score from 1.0 to 10.0.\n"
            "- Write a brief reasoning trace in reasonbook (internal use only)."
        )),
        ("human", "Abstract:\n\n{abstract}")
    ])

    criteria_formatted = "\n- ".join(state.get("distilled_criteria", []))
    result = (prompt | structured).invoke({
        "criteria": criteria_formatted,
        "abstract": state.get("raw_abstract", ""),
    })

    return {
        "evaluator_decision": result.decision,
        "evaluator_score": result.score,
        "evaluator_reasonbook": result.reasonbook,
    }


def node_critique(state: AgentState):
    """Reviews borderline papers against feedback_memory (user rejection history)."""
    memory = state.get("feedback_memory")
    if not memory or memory.strip() == "":
        return {
            "critique_decision": True,
            "critique_reasonbook": "Auto-passed: no rejection history exists.",
        }

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.0,
        api_key=settings.OPENAI_API_KEY,
    )
    structured = llm.with_structured_output(CritiqueOutput)

    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "You are reviewing a borderline paper recommendation.\n\n"
            "The evaluator was uncertain about this paper for this reason:\n"
            "{reasonbook}\n\n"
            "The user has historically rejected papers with these characteristics:\n"
            "{memory}\n\n"
            "If this paper's abstract matches what the user dislikes, output decision=False (reject).\n"
            "If it avoids the disliked elements, output decision=True (accept)."
        )),
        ("human", "Abstract:\n\n{abstract}")
    ])

    result = (prompt | structured).invoke({
        "reasonbook": state.get("evaluator_reasonbook", ""),
        "memory": memory,
        "abstract": state.get("raw_abstract", ""),
    })

    return {
        "critique_decision": result.decision,
        "critique_reasonbook": result.reasonbook,
    }


def route_evaluator(state: AgentState):
    decision = state.get("evaluator_decision")
    if decision == "accept":
        return END
    elif decision == "borderline":
        return "critique"
    return END  # reject


def route_critique(state: AgentState):
    return END  # always ends — decision stored in state


# Build Phase 1 graph
workflow = StateGraph(AgentState)
workflow.add_node("evaluator", node_evaluator)
workflow.add_node("critique", node_critique)
workflow.set_entry_point("evaluator")

workflow.add_conditional_edges(
    "evaluator",
    route_evaluator,
    {"critique": "critique", END: END},
)
workflow.add_edge("critique", END)

phase1_graph = workflow.compile()


async def run_deep_reader(markdown: str, distilled_criteria: list, feedback_memory: str) -> dict:
    """Phase 2: Deep Reader — full text + criteria + feedback → decision + score + explanation.

    Returns dict with keys: decision, score, explanation.
    """
    from app.agents.schemas import DeepReaderOutput

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.3,
        api_key=settings.OPENAI_API_KEY,
    )
    structured = llm.with_structured_output(DeepReaderOutput)

    criteria_formatted = "\n- ".join(distilled_criteria)

    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "You are an expert academic paper analyst. Read the full paper text and evaluate "
            "it against the user's research criteria.\n\n"
            "CRITERIA:\n{criteria}\n\n"
            "USER REJECTION HISTORY:\n{feedback_memory}\n\n"
            "INSTRUCTIONS:\n"
            "1. Determine if this paper is truly relevant based on its FULL content "
            "(not just abstract). Output 'accept' or 'reject'.\n"
            "2. Assign a final relevance score from 1.0 to 10.0.\n"
            "3. Write a 2-3 sentence explanation of WHY this paper is relevant to the user. "
            "This will be shown directly to the user in their feed.\n"
            "- If the paper scored well on abstract but the full text reveals it's not actually "
            "relevant, output 'reject' with a low score.\n"
            "- Papers with score below 5.0 will be filtered out."
        )),
        ("human", "Full paper text:\n\n{text}")
    ])

    # Truncate markdown to ~30k chars to stay within context limits
    truncated = markdown[:30000] if len(markdown) > 30000 else markdown

    result = (prompt | structured).invoke({
        "criteria": criteria_formatted,
        "feedback_memory": feedback_memory or "No rejection history.",
        "text": truncated,
    })

    return {
        "decision": result.decision,
        "score": result.score,
        "explanation": result.explanation,
    }
