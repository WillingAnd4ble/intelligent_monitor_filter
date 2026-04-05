"""
Bottom-up test for the explain chain: Modal Marker → Section Classifier → Deep Explainer.

Run from backend/:
    python test_explain_chain.py              # full chain
    python test_explain_chain.py --step 1     # only Marker extraction
    python test_explain_chain.py --step 2     # only Section Classifier (uses saved marker output)
    python test_explain_chain.py --step 3     # only Deep Explainer (uses saved classifier output)
"""

import argparse
import json
import time
from pathlib import Path

# Test with "Attention Is All You Need" — well-known, has clear sections
TEST_PDF_URL = "https://arxiv.org/pdf/1706.03762"
TEST_PAPER_TITLE = "Attention Is All You Need"
TEST_CONTENT_INTEREST = ["methodology", "experiments"]
TEST_FILTERING_GOAL = "Novel architectures for natural language processing"
TEST_LEVEL = "professional"

CACHE_DIR = Path("test_cache")


def step1_marker():
    """Test Modal Marker PDF extraction."""
    print("=" * 60)
    print("STEP 1: Marker PDF Extraction (Modal GPU)")
    print("=" * 60)

    from app.worker.modal_client import marker_extract_pdf

    start = time.time()
    text = marker_extract_pdf(TEST_PDF_URL)
    elapsed = time.time() - start

    if not text:
        print("FAIL — marker_extract_pdf returned empty string.")
        print("Check: MODAL_GPU_ENABLED=True in .env? Modal deployed?")
        return None

    print(f"OK — extracted {len(text)} chars in {elapsed:.1f}s")
    print(f"Lines: {len(text.splitlines())}")
    print(f"\nFirst 500 chars:\n{text[:500]}")
    print(f"\n...last 300 chars:\n{text[-300:]}")

    # Cache for next steps
    CACHE_DIR.mkdir(exist_ok=True)
    (CACHE_DIR / "marker_output.txt").write_text(text, encoding="utf-8")
    print(f"\nCached to {CACHE_DIR}/marker_output.txt")
    return text


def step2_classifier(text: str | None = None):
    """Test LLM Section Classifier."""
    print("\n" + "=" * 60)
    print("STEP 2: Section Classifier (gpt-4.1-nano)")
    print("=" * 60)

    if text is None:
        cache_file = CACHE_DIR / "marker_output.txt"
        if not cache_file.exists():
            print("FAIL — no cached marker output. Run step 1 first.")
            return None
        text = cache_file.read_text(encoding="utf-8")
        print(f"Loaded cached marker output ({len(text)} chars)")

    from app.agents.section_classifier import classify_sections

    start = time.time()
    filtered = classify_sections(text, TEST_CONTENT_INTEREST)
    elapsed = time.time() - start

    print(f"OK — filtered to {len(filtered)} chars in {elapsed:.1f}s")
    print(f"Content interest: {TEST_CONTENT_INTEREST}")
    print(f"Filtered/Original ratio: {len(filtered)/len(text)*100:.0f}%")
    print(f"\nFirst 500 chars of filtered text:\n{filtered[:500]}")

    # Cache for next step
    CACHE_DIR.mkdir(exist_ok=True)
    (CACHE_DIR / "classifier_output.txt").write_text(filtered, encoding="utf-8")
    print(f"\nCached to {CACHE_DIR}/classifier_output.txt")
    return filtered


def step3_explainer(filtered_text: str | None = None):
    """Test Deep Explanation LLM."""
    print("\n" + "=" * 60)
    print("STEP 3: Deep Explainer (gpt-5.4-nano)")
    print("=" * 60)

    if filtered_text is None:
        cache_file = CACHE_DIR / "classifier_output.txt"
        if not cache_file.exists():
            print("FAIL — no cached classifier output. Run step 2 first.")
            return None
        filtered_text = cache_file.read_text(encoding="utf-8")
        print(f"Loaded cached classifier output ({len(filtered_text)} chars)")

    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from pydantic import BaseModel, Field
    from app.core.config import settings

    class DeepExplanationOutput(BaseModel):
        explanation: str = Field(description="Markdown-formatted deep explanation, 300-600 words")

    level_instructions = {
        "professional": (
            "Write for an expert researcher. Use precise technical language, "
            "discuss methodology, experimental design, implications, and limitations. "
            "Assume domain knowledge."
        ),
        "student": (
            "Write for a university student. Explain key concepts, define acronyms, "
            "relate findings to the broader field, and walk through results step by step."
        ),
        "kid": (
            "Write in plain language for a curious 12-year-old. Use analogies, "
            "no jargon, and focus on what they did and why it matters."
        ),
    }

    llm = ChatOpenAI(
        model="gpt-5.4-nano-2026-03-17",
        temperature=0.7,
        api_key=settings.OPENAI_API_KEY,
    )
    structured = llm.with_structured_output(DeepExplanationOutput)

    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "You are writing a deep explanation of a scientific paper for a user. "
            "{level_instruction} "
            "The user's research goal: {filtering_goal}\n\n"
            "Write a 300-600 word markdown explanation with headers, bullets, and bold key terms. "
            "This should be a deep read, not a 3-sentence summary."
        )),
        ("human", (
            "Paper: {title}\n"
            "Authors: Vaswani et al.\n\n"
            "Relevant sections:\n{filtered_text}"
        )),
    ])

    chain = prompt | structured

    start = time.time()
    output = chain.invoke({
        "level_instruction": level_instructions[TEST_LEVEL],
        "filtering_goal": TEST_FILTERING_GOAL,
        "title": TEST_PAPER_TITLE,
        "filtered_text": filtered_text,
    })
    elapsed = time.time() - start

    print(f"OK — generated explanation in {elapsed:.1f}s")
    print(f"Level: {TEST_LEVEL}")
    print(f"Length: {len(output.explanation)} chars")
    print(f"\n{'─' * 40}")
    print(output.explanation)
    print(f"{'─' * 40}")

    # Cache
    CACHE_DIR.mkdir(exist_ok=True)
    (CACHE_DIR / "explanation_output.md").write_text(output.explanation, encoding="utf-8")
    print(f"\nCached to {CACHE_DIR}/explanation_output.md")
    return output.explanation


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test explain chain step by step")
    parser.add_argument("--step", type=int, choices=[1, 2, 3], help="Run only this step (default: all)")
    args = parser.parse_args()

    if args.step == 1:
        step1_marker()
    elif args.step == 2:
        step2_classifier()
    elif args.step == 3:
        step3_explainer()
    else:
        # Full chain
        text = step1_marker()
        if text:
            filtered = step2_classifier(text)
            if filtered:
                step3_explainer(filtered)

    print("\nDone.")