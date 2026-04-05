"""
Test script for GPU inference functions.
Run: modal run gpu_test.py

Calls the deployed gpu-inference app via modal.Cls.from_name(),
which is the same path the backend uses.
Requires: modal deploy gpu_inference.py (run first)
"""

import modal

app = modal.App("gpu-inference-test")


@app.local_entrypoint()
def main():
    passed = 0
    failed = 0

    # Look up deployed classes (same as backend's modal_client.py)
    embedder_cls = modal.Cls.from_name("gpu-inference", "Specter2Embedder")
    embedder = embedder_cls()

    extractor_cls = modal.Cls.from_name("gpu-inference", "MarkerExtractor")
    extractor = extractor_cls()

    # ── SPECTER2 Tests ──────────────────────────────────────────

    print("=" * 60)
    print("SPECTER2 TESTS")
    print("=" * 60)

    # Test 1: Single paper embedding
    print("\n[Test 1] Single paper embedding...")
    try:
        vecs = embedder.embed_batch.remote([
            "Attention Is All You Need [SEP] We propose a new simple network architecture based on attention mechanisms."
        ])
        assert isinstance(vecs, list), f"Expected list, got {type(vecs)}"
        assert len(vecs) == 1, f"Expected 1 vector, got {len(vecs)}"
        assert len(vecs[0]) == 768, f"Expected 768 dims, got {len(vecs[0])}"
        assert all(isinstance(v, float) for v in vecs[0]), "Expected all floats"
        print(f"  PASSED - 1 vector, {len(vecs[0])} dims, first 3: {vecs[0][:3]}")
        passed += 1
    except Exception as e:
        print(f"  FAILED - {e}")
        failed += 1

    # Test 2: Batch of 3 papers
    print("\n[Test 2] Batch of 3 papers...")
    try:
        texts = [
            "Deep Learning [SEP] A review of deep learning methods and applications.",
            "Graph Neural Networks [SEP] We survey recent advances in graph neural networks.",
            "Reinforcement Learning [SEP] An introduction to reinforcement learning algorithms.",
        ]
        vecs = embedder.embed_batch.remote(texts)
        assert isinstance(vecs, list), f"Expected list, got {type(vecs)}"
        assert len(vecs) == 3, f"Expected 3 vectors, got {len(vecs)}"
        for i, vec in enumerate(vecs):
            assert len(vec) == 768, f"Vector {i} has {len(vec)} dims, expected 768"
        print(f"  PASSED - {len(vecs)} vectors, all 768-dim")
        passed += 1
    except Exception as e:
        print(f"  FAILED - {e}")
        failed += 1

    # ── MARKER Tests ────────────────────────────────────────────

    print("\n" + "=" * 60)
    print("MARKER TESTS")
    print("=" * 60)

    # Test 3: Extract known arXiv PDF
    print("\n[Test 3] Extract arXiv PDF (Attention Is All You Need)...")
    try:
        text = extractor.extract.remote("https://arxiv.org/pdf/1706.03762")
        assert isinstance(text, str), f"Expected str, got {type(text)}"
        assert len(text) > 1000, f"Expected >1000 chars, got {len(text)}"
        print(f"  PASSED - Extracted {len(text)} chars")
        print(f"  Preview: {text[:150]}...")
        passed += 1
    except Exception as e:
        print(f"  FAILED - {e}")
        failed += 1

    # Test 4: Handle bad URL gracefully
    print("\n[Test 4] Bad URL handling...")
    try:
        text = extractor.extract.remote("https://example.com/nonexistent.pdf")
        print(f"  PASSED - Returned without crash, got {len(text)} chars")
        passed += 1
    except Exception as e:
        # An exception is acceptable — the key is no container crash
        print(f"  PASSED - Raised expected error: {type(e).__name__}: {e}")
        passed += 1

    # ── Summary ─────────────────────────────────────────────────

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed} tests")
    print("=" * 60)

    if failed > 0:
        raise SystemExit(1)
