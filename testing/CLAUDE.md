# CLAUDE.md — TheArXivist Test & Benchmark Engine

## Project Overview
Multi-agent arXiv filtering system. Your role is exclusively building 
the pytest suite and Streamlit benchmarking tool. Do not modify 
FastAPI routes or LangGraph nodes.

## Directory Layout
├── backend/              # FastAPI backend (read-only for you) and agents are there
├── web_ui/               # The whole next.js frontend
├── testing/ <--- YOU WORK HERE
    ├── CLAUDE.md
	├── tests/                # Your pytest output goes here
	├── benchmark/            # Your Streamlit tool goes here
	├── evaluation_dataset.json  # Static ground truth fixture
    ├── UNIT_TESTING_SPECIFICATION.md
    ├── EVALUATION_BENCHMARK_SPECIFICATION.md
    ├── API_SPECIFICATION.md
    └── AGENT_ARCHITECTURE_SPECIFICATION.md

## Hard Constraints
- NEVER call real Claude/Anthropic API in any test — mock all LLM calls
- NEVER write to the production database — use pytest fixtures with SQLite
- NEVER import Modal.com in benchmark tool — dataset is pre-extracted JSON
- All async tests use pytest-asyncio with asyncio_mode = "auto"

## Conventions
- Mock target: patch at the point of import, not the source module
- Pydantic models are in backend/agents/schemas.py — import from there, never redefine
- API base URL in tests: http://testserver via FastAPI TestClient
- Token cost calculation: input tokens × $0.000003, output × $0.000015 (Claude Sonnet)

## What to Read First
1. AGENT_ARCHITECTURE_SPECIFICATION.md — Pydantic contracts and node I/O
2. UNIT_TESTING_SPECIFICATION.md — exact test names and assertions required
3. API_SPECIFICATION.md — endpoint shapes for TestClient tests
4. EVALUATION_BENCHMARK_SPECIFICATION.md — experiment configs and metrics

## Backend Reference (Read-Only)
The implemented backend lives at ../backend/ — read it to understand 
actual import paths and function signatures before writing mocks. 
Do not modify anything there.