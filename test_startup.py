#!/usr/bin/env python3
"""
Test script to verify embedder pre-loading at startup.

This simulates the startup sequence to ensure the model loads correctly.
"""

import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_embedder_preload():
    """Test that embedder loads and performs inference."""
    logger.info("Testing embedder pre-load...")
    
    start_time = time.time()
    
    # Import and initialize embedder
    from src.embeddings.embedder import LocalEmbedder
    embedder = LocalEmbedder()
    
    # Force model loading with warmup
    logger.info("Performing warmup embedding...")
    embedding = embedder.embed_text("warmup")
    
    load_time = time.time() - start_time
    logger.info(f"✓ Model loaded in {load_time:.2f} seconds")
    
    # Verify embedding dimensions
    assert embedding.shape[0] == 384, f"Expected 384 dimensions, got {embedding.shape[0]}"
    logger.info(f"✓ Embedding dimensions correct: {embedding.shape[0]}")
    
    # Test actual query embedding
    start_time = time.time()
    query_embedding = embedder.embed_query("What are the risk factors?")
    query_time = time.time() - start_time
    
    logger.info(f"✓ Query embedding generated in {query_time:.3f} seconds")
    assert query_embedding.shape[0] == 384
    
    # Verify model is loaded (not None)
    assert embedder._model is not None, "Model should be loaded"
    logger.info("✓ Model is loaded and ready")
    
    logger.info("\n✅ All tests passed!")
    logger.info(f"   - Initial load time: {load_time:.2f}s")
    logger.info(f"   - Subsequent query time: {query_time:.3f}s")
    logger.info(f"   - Speedup: {load_time/query_time:.1f}x faster after warmup")

if __name__ == "__main__":
    test_embedder_preload()
