"""
Modal GPU Inference App
=======================
Deployed functions for SPECTER2 embeddings and MARKER PDF extraction.

Deploy:  modal deploy gpu_inference.py
Test:    modal run gpu_inference.py
"""

import modal

app = modal.App("gpu-inference")

# ── Container Images ──────────────────────────────────────────────

specter2_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch>=2.1.0",
        "transformers>=4.38.0",
        "adapters>=0.2.0",
    )
)

marker_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1-mesa-glx", "libglib2.0-0", "poppler-utils")
    .pip_install(
        "marker-pdf>=1.0.0",
        "torch>=2.1.0",
    )
)


# ── SPECTER2 Embeddings ──────────────────────────────────────────

@app.cls(
    image=specter2_image,
    gpu="T4",
    scaledown_window=60,   # shutdown 60s after last call (not 5 min)
    timeout=120,                 # kill any single call stuck longer than 2 min
    max_containers=2,         # max 2 containers at once (cost ceiling)
    secrets=[modal.Secret.from_name("huggingface")],
    retries=modal.Retries(max_retries=2, backoff_coefficient=2.0),
)
class Specter2Embedder:
    """
    Encodes paper title+abstract pairs into 768-dim embeddings
    using allenai/specter2_base with the proximity adapter.

    Input format per text: "title [SEP] abstract"
    """

    @modal.enter()
    def load_model(self):
        import os
        import torch
        from transformers import AutoTokenizer
        from adapters import AutoAdapterModel

        hf_token = os.environ.get("HF_TOKEN")
        self.tokenizer = AutoTokenizer.from_pretrained("allenai/specter2_base", token=hf_token)
        self.model = AutoAdapterModel.from_pretrained("allenai/specter2_base", token=hf_token)
        self.model.load_adapter(
            "allenai/specter2", source="hf", load_as="specter2", set_active=True
        )
        self.model.eval()
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model.to(self.device)

    @modal.method()
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Encode a batch of "title [SEP] abstract" strings.
        Returns list of 768-dim float vectors.
        """
        import torch

        inputs = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        ).to(self.device)

        with torch.no_grad():
            output = self.model(**inputs)

        # CLS token pooling -> 768-dim embedding per input
        embeddings = output.last_hidden_state[:, 0, :]
        return embeddings.cpu().tolist()


# ── MARKER PDF Extraction ────────────────────────────────────────

@app.cls(
    image=marker_image,
    gpu="T4",
    scaledown_window=60,   # shutdown 60s after last call
    timeout=180,                 # 3 min max per PDF (download + OCR)
    max_containers=3,         # max 3 containers (MARKER is called per-paper)
    retries=modal.Retries(max_retries=2, backoff_coefficient=2.0),
)
class MarkerExtractor:
    """
    Downloads a PDF by URL and extracts full text as markdown
    using the MARKER OCR/PDF pipeline.
    """

    @modal.enter()
    def load_model(self):
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        from marker.config.parser import ConfigParser

        config_parser = ConfigParser({"output_format": "markdown"})
        self.converter = PdfConverter(
            config=config_parser.generate_config_dict(),
            artifact_dict=create_model_dict(),
            processor_list=config_parser.get_processors(),
            renderer=config_parser.get_renderer(),
        )

    @modal.method()
    def extract(self, pdf_url: str) -> str:
        """Download PDF from url and return extracted markdown text."""
        import urllib.request
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            tmp_path = f.name

        try:
            urllib.request.urlretrieve(pdf_url, tmp_path)
            rendered = self.converter(tmp_path)
            from marker.output import text_from_rendered
            text, _, _ = text_from_rendered(rendered)
            return text
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


# ── Local test entrypoint ────────────────────────────────────────

@app.local_entrypoint()
def main():
    """Quick smoke test: modal run gpu_inference.py"""
    print("--- SPECTER2 test ---")
    embedder = Specter2Embedder()
    vecs = embedder.embed_batch.remote([
        "Attention Is All You Need [SEP] We propose a new simple network architecture based on attention mechanisms."
    ])
    print(f"Embedding dim: {len(vecs[0])}, first 5 values: {vecs[0][:5]}")

    print("\n--- MARKER test ---")
    extractor = MarkerExtractor()
    text = extractor.extract.remote("https://arxiv.org/pdf/1706.03762")
    print(f"Extracted {len(text)} chars, first 200:\n{text[:200]}")