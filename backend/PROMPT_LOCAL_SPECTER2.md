# Backend Instance — Local CPU SPECTER2 + Fix Query Embeddings

Read CLAUDE.md first.

## Context

SPECTER2 is a 110M parameter model (BERT-base sized). Running it on Modal GPU is overkill for our use case — we process 50-200 papers once per day in a background Celery task. Local CPU inference takes ~1-2 minutes for a batch, which is perfectly fine for a background job.

Currently `modal_client.py` has two modes:
- `MODAL_GPU_ENABLED=True` → calls Modal cloud
- `MODAL_GPU_ENABLED=False` → returns **random mock vectors** (useless for actual search)

We need a third mode: **local CPU inference** that generates real embeddings without Modal.

There's also a critical bug: the pipeline's RRF search uses `[0.0]*768` as the query embedding (`celery_app.py` line 121-122), which kills the semantic search leg entirely. This task fixes that too.

## Task 1: Add `SPECTER2_LOCAL` config flag

In `app/core/config.py`, add to the `Settings` class:

```python
SPECTER2_LOCAL: bool = True  # default True: run SPECTER2 on local CPU
```

Place it near the other Modal settings.

## Task 2: Add local CPU SPECTER2 inference to `app/worker/modal_client.py`

The priority order for `specter2_embed_batch()` should be:

```
1. MODAL_GPU_ENABLED=True  → Modal cloud (fast, costs money)
2. SPECTER2_LOCAL=True      → Local CPU torch (free, ~1min for 200 papers)
3. Both False               → Mock vectors (unit testing only)
```

### Implementation:

Add a module-level lazy-loaded model holder:

```python
_local_specter2 = None

def _get_local_specter2():
    """Lazy-load SPECTER2 model on first call. Stays in memory for subsequent calls."""
    global _local_specter2
    if _local_specter2 is not None:
        return _local_specter2
    
    import torch
    from transformers import AutoTokenizer
    from adapters import AutoAdapterModel
    
    logger.info("Loading SPECTER2 model locally (CPU)...")
    tokenizer = AutoTokenizer.from_pretrained("allenai/specter2_base")
    model = AutoAdapterModel.from_pretrained("allenai/specter2_base")
    model.load_adapter("allenai/specter2", source="hf", load_as="specter2", set_active=True)
    model.eval()
    
    _local_specter2 = (tokenizer, model)
    logger.info("SPECTER2 model loaded successfully")
    return _local_specter2


def _embed_local(texts: list[str]) -> list[list[float]]:
    """Run SPECTER2 inference on local CPU."""
    import torch
    
    tokenizer, model = _get_local_specter2()
    
    inputs = tokenizer(
        texts,
        padding=True,
        truncation=True,
        max_length=512,
        return_tensors="pt",
    )
    
    with torch.no_grad():
        output = model(**inputs)
    
    # CLS token pooling → 768-dim embedding per input
    embeddings = output.last_hidden_state[:, 0, :]
    return embeddings.tolist()
```

This mirrors exactly what `gpu/gpu_inference.py` `Specter2Embedder` does — same model, same tokenizer, same CLS pooling. Just on CPU instead of GPU.

### Modify `specter2_embed_batch()`:

```python
def specter2_embed_batch(title_abstract_pairs: list[dict]) -> list[list[float]]:
    texts = [
        f"{p['title']} [SEP] {p['abstract']}" for p in title_abstract_pairs
    ]

    # Priority 1: Modal GPU
    if _is_modal_ready():
        import modal
        logger.info(f"Calling Modal SPECTER2 for {len(texts)} papers")
        cls = modal.Cls.from_name(MODAL_APP_NAME, "Specter2Embedder")
        embedder = cls()
        return embedder.embed_batch.remote(texts)

    # Priority 2: Local CPU
    if settings.SPECTER2_LOCAL:
        logger.info(f"Running SPECTER2 locally (CPU) for {len(texts)} papers")
        return _embed_local(texts)

    # Priority 3: Mock (testing only)
    logger.warning("SPECTER2 disabled — returning mock embeddings")
    return [[random.uniform(-0.1, 0.1) for _ in range(768)] for _ in texts]
```

**Important**: Keep the function signature identical — `specter2_embed_batch(title_abstract_pairs: list[dict]) -> list[list[float]]`. Don't change what callers pass in or receive.

### Batch size consideration

For large batches (200+ papers), process in chunks to avoid memory issues on CPU:

```python
BATCH_SIZE = 32  # papers per forward pass on CPU

def _embed_local(texts: list[str]) -> list[list[float]]:
    import torch
    
    tokenizer, model = _get_local_specter2()
    all_embeddings = []
    
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        inputs = tokenizer(
            batch,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        )
        with torch.no_grad():
            output = model(**inputs)
        embeddings = output.last_hidden_state[:, 0, :]
        all_embeddings.extend(embeddings.tolist())
    
    return all_embeddings
```

## Task 3: Fix the RRF query embedding in `app/worker/celery_app.py`

In the `trigger_agent_discovery` task, around line 120-128, replace:

```python
# 3. Hybrid RRF Search mapping mock arrays locally
mock_query_embed = [0.0] * 768
candidates = await perform_hybrid_rrf_search(
    session=session,
    query_text=user_settings.filtering_goal or "AI Agents",
    query_embedding=mock_query_embed,
    limit=10,
    rrf_k=60
)
```

With:

```python
# 3. Generate real query embedding from filtering_goal, then run Hybrid RRF Search
from app.worker.modal_client import specter2_embed_batch

query_text = user_settings.filtering_goal or "AI Agents"
query_embedding = specter2_embed_batch([{"title": query_text, "abstract": ""}])[0]

candidates = await perform_hybrid_rrf_search(
    session=session,
    query_text=query_text,
    query_embedding=query_embedding,
    limit=10,
    rrf_k=60
)
```

This generates a real 768-dim embedding for the user's filtering goal, making the semantic search leg of RRF actually functional. `specter2_embed_batch` handles the Modal vs local vs mock routing automatically.

## Task 4: Add dependencies to `requirements.txt`

Add these under a new section:

```
# Local SPECTER2 inference (CPU)
torch>=2.1.0
transformers>=4.38.0
adapters>=0.2.0
```

Note: `torch` is ~2GB. This is the tradeoff for free local inference. If the user doesn't want it, `SPECTER2_LOCAL=False` skips the import entirely (torch is only imported inside `_get_local_specter2()`, not at module level).

## What NOT to Touch
- `app/agents/graph.py` — pipeline graph is separate
- `app/worker/modal_client.py` marker functions — only modify SPECTER2 section
- `gpu/` directory — separate instance manages Modal deployment
- `app/api/` endpoints — no API changes needed
- `app/agents/section_classifier.py` — unrelated

## File Summary
| Action | File |
|--------|------|
| **Add config** | `app/core/config.py` — add `SPECTER2_LOCAL: bool = True` |
| **Rewrite** | `app/worker/modal_client.py` — add local CPU inference path |
| **Fix** | `app/worker/celery_app.py` — replace `[0.0]*768` with real query embedding |
| **Add deps** | `requirements.txt` — add torch, transformers, adapters |

## .env Addition
```
SPECTER2_LOCAL=True
```
This is the default, so it works even without adding it to .env.