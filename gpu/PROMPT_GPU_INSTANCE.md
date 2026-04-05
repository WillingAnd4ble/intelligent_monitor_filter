ON CONSIDERATION WHETHER TO IMPLEMENT. [DONT'T TOUCH YET]

# GPU Instance — Finalize Modal Deployment

Read CLAUDE.md first.

## Context
`gpu_inference.py` is already built with `Specter2Embedder` and `MarkerExtractor` classes. The backend already has a client (`../backend/app/worker/modal_client.py`) that calls these via `modal.Cls.from_name("gpu-inference", "ClassName")`. You do NOT need to modify the backend.

## Task 1: Add HuggingFace Secret to Specter2Embedder

`allenai/specter2_base` is a public HuggingFace model, but anonymous downloads get rate-limited. Cold starts fail intermittently without a token.

In `gpu_inference.py`:
1. Add `secrets=[modal.Secret.from_name("huggingface")]` to the `@app.cls()` decorator of `Specter2Embedder`
2. In `load_model()`, read the token and pass it to the model download:
```python
import os
hf_token = os.environ.get("HF_TOKEN")
self.tokenizer = AutoTokenizer.from_pretrained("allenai/specter2_base", token=hf_token)
self.model = AutoAdapterModel.from_pretrained("allenai/specter2_base", token=hf_token)
self.model.load_adapter("allenai/specter2", source="hf", load_as="specter2", set_active=True)
```

The secret is created on Modal CLI separately: `modal secret create huggingface HF_TOKEN=hf_xxx`
The code should still work if the secret isn't set (token=None falls back to anonymous download).

## Task 2: Verify Marker API Compatibility

The current code uses:
```python
from marker.converters.pdf import PdfConverter
from marker.config.parser import ConfigParser

config = ConfigParser({"output_format": "markdown"})
self.converter = PdfConverter(config=config.generate_config_dict())
result = self.converter(tmp_path)
return result.markdown
```

Check that these imports and API calls are correct for `marker-pdf>=1.0.0`. The Marker SDK has changed APIs between versions. If the current pattern is wrong, fix it. If you can't verify locally, add a comment noting the API version assumption and add a try/except fallback.

## Task 3: Add Retries

Add retry configuration to both classes for robustness:
```python
@app.cls(
    ...existing params...,
    retries=modal.Retries(max_retries=2, backoff_coefficient=2.0),
)
```

## Task 4: Write Real Tests in gpu_test.py

Replace the current `gpu_test.py` (which is a copy of `get_started.py`) with a proper test script:

```python
"""
Test script for GPU inference functions.
Run: modal run gpu_test.py
"""
```

Tests to include:
1. **SPECTER2 single paper** — embed one `"title [SEP] abstract"` string, assert output is a list of 768 floats
2. **SPECTER2 batch** — embed 3 papers, assert 3 vectors returned, all 768-dim
3. **MARKER extraction** — extract a known arXiv PDF (e.g. `https://arxiv.org/pdf/1706.03762`), assert output is a non-empty string with length > 1000 chars
4. **MARKER handles bad URL** — pass an invalid URL, verify it raises or returns empty gracefully (no container crash)

Use the local entrypoint pattern:
```python
@app.local_entrypoint()
def main():
    # run all tests, print results
```

## Task 5: Update requirements.txt

Add any missing dependencies. Currently only has `modal>=0.67.0`. If you need anything else for testing, add it.

## Do NOT
- Modify any files in `../backend/` — a separate instance manages that
- Change the app name `"gpu-inference"` — the backend client depends on it
- Change class names `Specter2Embedder` or `MarkerExtractor` — the backend client depends on them
- Change method signatures (`embed_batch(texts: list[str])` and `extract(pdf_url: str)`) — the backend client depends on them