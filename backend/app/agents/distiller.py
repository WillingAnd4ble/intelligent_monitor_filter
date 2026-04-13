from pydantic import BaseModel, Field
from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.core.config import settings

class DistilledCriteriaOutput(BaseModel):
    distilled_criteria: List[str] = Field(description="Strict list of exact context inclusion thresholds tracking user parameters.")
    lexical_query: str = Field(description="Short keyword query (3-8 key terms) optimized for BM25 full-text search. No filler words, only domain-specific terms and phrases.")

def run_goal_distiller(categories: List[str], topics: List[str], content_interest: List[str], filtering_goal: str) -> DistilledCriteriaOutput:
    """Generates precise filtering criteria and a lexical search query from user's research interests."""
    if not filtering_goal and not content_interest:
        return DistilledCriteriaOutput(distilled_criteria=[], lexical_query="")
        
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.0,
        api_key=settings.OPENAI_API_KEY
    )
    
    structured_llm = llm.with_structured_output(DistilledCriteriaOutput)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "You are an alignment AI. Translate the user's generalized research interests into:\n"
            "1. A hyper-specific, binary list of criteria (3-7) that a downstream AI Evaluator can easily check off. "
            "Be absolute and restrictive.\n"
            "2. A short lexical_query (3-8 domain-specific key terms) for BM25 full-text search against paper titles "
            "and abstracts. Use only precise technical terms, no filler words. Example: 'multi-agent LLM collaboration "
            "tool-use benchmark evaluation'."
        )),
        ("human", (
            "Categories: {categories}\n"
            "Topics: {topics}\n"
            "Interests: {interests}\n"
            "Primary Goal: {goal}\n\n"
            "Distill this into an exact Criteria array."
        ))
    ])
    
    chain = prompt | structured_llm
    
    result = chain.invoke({
        "categories": categories,
        "topics": topics,
        "interests": content_interest,
        "goal": filtering_goal
    })
    
    return result
