from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.agents.schemas import AgentState, EvaluatorOutput, CritiqueOutput, ExplainerOutput, RankerOutput
from app.core.config import settings

def node_evaluator(state: AgentState):
    """Fast funnel evaluating abstracts explicitly against mapped criteria."""
    llm = ChatOpenAI(
        model="gpt-4o-mini", 
        temperature=0.0, 
        api_key=settings.OPENAI_API_KEY
    )
    
    structured_evaluator = llm.with_structured_output(EvaluatorOutput)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "You are an elite academic recommender AI. Evaluate incoming publications "
            "strictly against the user's specific inclusion/exclusion bounds:\n"
            "{criteria}\n\n"
            "If paper inherently serves the central goal, output 'accept'.\n"
            "If paper touches bounds broadly but isn't centrally focused, output 'borderline'.\n"
            "If paper violates exclusions or misses entirely, output 'reject'."
        )),
        ("human", "Evaluate the following extracted text:\n\n{text}")
    ])
    
    chain = prompt | structured_evaluator
    
    criteria_formatted = "\n- ".join(state.get("distilled_criteria", []))
    target_eval_text = state.get("sectioned_text") or state.get("raw_abstract", "")
    
    result = chain.invoke({
        "criteria": criteria_formatted, 
        "text": target_eval_text
    })
    
    return {
        "evaluator_decision": result.decision,
        "evaluator_reasonbook": result.reasonbook
    }

def node_critique(state: AgentState):
    """Double checks borderline traces actively against strict 'feedback_memory' overrides."""
    memory = state.get("feedback_memory")
    if not memory or memory.strip() == "":
        return {
            "critique_decision": True,
            "critique_reasonbook": "Auto-passed: No historical rejection memory exists to contradict Evaluator."
        }
        
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.0,
        api_key=settings.OPENAI_API_KEY
    )
    
    structured_critique = llm.with_structured_output(CritiqueOutput)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "You are an alignment AI tasked with overriding a junior agent's recommendation.\n"
            "The junior agent was 'borderline' unsure about this paper for the following reason:\n"
            "{reasonbook}\n\n"
            "CRITICAL DIRECTIVE:\n"
            "The user historically absolutely DESPISES these elements: {memory}\n\n"
            "If the junior agent's reason or the paper's abstract heavily features what the user despises, "
            "you MUST output decision=False (Reject).\n"
            "If it circumvents the despised elements safely, output decision=True (Accept)."
        )),
        ("human", "Evaluate against Memory. Abstract context:\n\n{text}")
    ])
    
    chain = prompt | structured_critique
    
    target_eval_text = state.get("sectioned_text") or state.get("raw_abstract", "")
    reasonbook = state.get("evaluator_reasonbook", "No specific reason provided.")
    
    result = chain.invoke({
        "reasonbook": reasonbook,
        "memory": memory,
        "text": target_eval_text
    })
    
    return {
        "critique_decision": result.decision,
        "critique_reasonbook": result.reasonbook
    }

def node_pdf_extractor(state: AgentState):
    """Extracts full PDF text via MARKER on Modal GPU. Falls back to abstract."""
    from app.worker.modal_client import marker_extract_pdf

    pdf_url = state.get("pdf_url")
    if pdf_url:
        extracted = marker_extract_pdf(pdf_url)
        if extracted:
            return {"extracted_pdf_text": extracted}

    # Fallback: use abstract if no PDF URL or extraction failed
    return {"extracted_pdf_text": state.get("raw_abstract", "")}

def node_section_classifier(state: AgentState):
    """Regex + LLM Slices grouping document context onto specific User bounds."""
    # MOCKED: Passthrough locally reducing GPU latency boundaries
    return {"sectioned_text": state.get("extracted_pdf_text", "")}

def node_explainer(state: AgentState):
    """Compiles the final library explanation rationale natively saving caching logic."""
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7, api_key=settings.OPENAI_API_KEY)
    structured = llm.with_structured_output(ExplainerOutput)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Write a maximum 3 sentence explanation focusing on why this text strictly matches user criteria: {criteria}"),
        ("human", "Text Context:\n{text}")
    ])
    res = (prompt | structured).invoke({"criteria": "\n".join(state.get("distilled_criteria", [])), "text": state.get("sectioned_text") or state.get("raw_abstract", "")})
    return {"final_explanation": res.explanation}

def node_ranker(state: AgentState):
    """Scores final qualitative boundaries outputting numeric bounds."""
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0, api_key=settings.OPENAI_API_KEY)
    structured = llm.with_structured_output(RankerOutput)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Score this abstract mapping relevance to criteria (1.0 to 10.0 float) solely based on logical matching intensity: {criteria}"),
        ("human", "{text}")
    ])
    res = (prompt | structured).invoke({"criteria": "\n".join(state.get("distilled_criteria", [])), "text": state.get("sectioned_text") or state.get("raw_abstract", "")})
    return {"agent_score": res.score}

def route_evaluator_decision(state: AgentState):
    decision = state.get("evaluator_decision")
    if decision == "accept":
        return "pdf_extractor" 
    elif decision == "borderline":
        return "critique"
    return END

def route_critique_decision(state: AgentState):
    if state.get("critique_decision") is True:
        return "pdf_extractor"
    return END

workflow = StateGraph(AgentState)

workflow.add_node("evaluator", node_evaluator)
workflow.add_node("critique", node_critique)
workflow.add_node("pdf_extractor", node_pdf_extractor)
workflow.add_node("section_classifier", node_section_classifier)
workflow.add_node("explainer", node_explainer)
workflow.add_node("ranker", node_ranker)

workflow.set_entry_point("evaluator")

workflow.add_conditional_edges(
    "evaluator",
    route_evaluator_decision,
    {
        "pdf_extractor": "pdf_extractor",
        "critique": "critique",
        END: END
    }
)
workflow.add_conditional_edges(
    "critique",
    route_critique_decision,
    {
        "pdf_extractor": "pdf_extractor",
        END: END
    }
)

workflow.add_edge("pdf_extractor", "section_classifier")
workflow.add_edge("section_classifier", "explainer")
workflow.add_edge("explainer", "ranker")
workflow.add_edge("ranker", END)

app = workflow.compile()
