"""Multi-provider LLM call factory.

Routing rules for `model` strings:
- Contains '/'  (e.g. 'anthropic/claude-3.5-sonnet')  -> OpenRouter
- Starts with 'claude-'                                -> Anthropic direct
- Anything else                                        -> OpenAI direct
The OpenRouter path uses ChatOpenAI with a custom base_url, exploiting
OpenRouter's OpenAI-compatible API. Requires OPENROUTER_API_KEY in env.

Returns parsed structured output + (tokens_in, tokens_out, latency_ms).
Used by runner.py for evaluator/critique/deep_reader calls and by Page 5
for distiller experiments.
"""

import os
import time
from typing import Tuple, Type

from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def is_openrouter_model(model: str) -> bool:
    return "/" in model


def _build_llm(model: str, temperature: float = 0.0):
    if is_openrouter_model(model):
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError(
                f"Model '{model}' looks like an OpenRouter id but "
                "OPENROUTER_API_KEY is not set. Add it to testing/.env.benchmark."
            )
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            base_url=OPENROUTER_BASE_URL,
            api_key=api_key,
            default_headers={
                # Optional but recommended by OpenRouter for analytics
                "HTTP-Referer": "https://localhost/benchmark-harness",
                "X-Title": "arXiv Filtering Benchmark",
            },
        )
    if model.startswith("claude-"):
        return ChatAnthropic(model=model, temperature=temperature)
    # Default: OpenAI (covers gpt-4o-mini and gpt-5.4-nano-*)
    return ChatOpenAI(model=model, temperature=temperature)


def call_structured(
    model: str,
    output_schema: Type[BaseModel],
    system_template: str,
    human_template: str,
    template_vars: dict,
    temperature: float = 0.0,
) -> Tuple[BaseModel, int, int, float]:
    """Run a structured-output LLM call.

    Returns: (parsed_output, tokens_in, tokens_out, latency_ms)
    Tokens are read from response metadata; if unavailable, returns 0/0
    and the caller can estimate from input/output character length.
    """
    llm = _build_llm(model, temperature=temperature)
    structured = llm.with_structured_output(output_schema, include_raw=True)

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        ("human", human_template),
    ])

    t0 = time.perf_counter()
    result = (prompt | structured).invoke(template_vars)
    latency_ms = (time.perf_counter() - t0) * 1000.0

    parsed = result["parsed"]
    raw = result.get("raw")
    tokens_in = 0
    tokens_out = 0
    if raw is not None and getattr(raw, "usage_metadata", None):
        tokens_in = int(raw.usage_metadata.get("input_tokens", 0))
        tokens_out = int(raw.usage_metadata.get("output_tokens", 0))
    return parsed, tokens_in, tokens_out, latency_ms
