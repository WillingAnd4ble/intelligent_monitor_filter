"""
Section classifier for deep explanations.

Uses an LLM to identify section boundaries in a full paper text,
then filters to only sections matching the user's content_interest.
"""

import logging
from typing import Literal

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.core.config import settings

logger = logging.getLogger(__name__)


class SectionEntry(BaseModel):
    section_name: str = Field(description="Actual heading from paper, e.g. '3.1 Our Approach'")
    category: Literal["introduction", "methodology", "experiments", "conclusions", "other"]
    start_line: int
    end_line: int


class TableOfContents(BaseModel):
    sections: list[SectionEntry]


def classify_sections(full_text: str, content_interest: list[str]) -> str:
    """Classify paper sections via LLM and filter to user's content_interest.

    Args:
        full_text: The full extracted paper text.
        content_interest: List of section categories the user cares about,
            e.g. ["methodology", "experiments"].

    Returns:
        Filtered text containing only sections matching content_interest,
        or the full text if classification fails or filtering yields nothing.
    """
    lines = full_text.split("\n")

    # Short papers: skip classification
    if len(lines) < 50:
        return full_text

    # Prepend line numbers
    numbered_text = "\n".join(f"{i+1}: {line}" for i, line in enumerate(lines))

    try:
        llm = ChatOpenAI(
            model="gpt-4.1-nano",
            temperature=0.0,
            api_key=settings.OPENAI_API_KEY,
        )
        structured = llm.with_structured_output(TableOfContents)

        prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "You are a scientific paper analyst. Given a paper's full text with line numbers, "
                "identify all section boundaries. Map each section to exactly one of these categories: "
                "introduction, methodology, experiments, conclusions, other. "
                "Return the table of contents as structured JSON."
            )),
            ("human", "{numbered_text}"),
        ])

        chain = prompt | structured
        toc: TableOfContents = chain.invoke({"numbered_text": numbered_text})

    except Exception:
        logger.warning("Section classification LLM call failed, returning full text", exc_info=True)
        return full_text

    # Filter sections by content_interest
    if not content_interest:
        return full_text

    matching = [entry for entry in toc.sections if entry.category in content_interest]

    if not matching:
        return full_text

    # Slice and concatenate matching sections
    parts: list[str] = []
    for entry in matching:
        section_lines = lines[entry.start_line - 1 : entry.end_line]
        parts.append(f"## {entry.section_name}\n" + "\n".join(section_lines))

    return "\n\n".join(parts)
