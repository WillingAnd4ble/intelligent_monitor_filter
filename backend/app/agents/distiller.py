from pydantic import BaseModel, Field
from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.core.config import settings

class DistilledCriteriaOutput(BaseModel):
    distilled_criteria: List[str] = Field(description="Strict list of exact context inclusion thresholds tracking user parameters.")

def run_goal_distiller(categories: List[str], topics: List[str], content_interest: List[str], filtering_goal: str) -> List[str]:
    """Generates precise filtering rules asynchronously replacing raw UI strings with concrete LLM checking logic."""
    if not filtering_goal and not content_interest:
        return []
        
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.0,
        api_key=settings.OPENAI_API_KEY
    )
    
    structured_llm = llm.with_structured_output(DistilledCriteriaOutput)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "You are an alignment AI. Translate the user's generalized research interests into a hyper-specific, "
            "binary list of criteria that a downstream AI Evaluator can easily check off.\n"
            "Keep criteria between 3 and 7 exact requirements. Be absolute and restrictive."
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
    
    return result.distilled_criteria
