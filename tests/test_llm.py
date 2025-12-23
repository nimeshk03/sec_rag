import os
import pytest
from unittest.mock import patch, MagicMock

def test_llm_client_initialization():
    """Test LLM client can be initialized with Groq."""
    with patch.dict(os.environ, {
        "LLM_PROVIDER": "groq",
        "GROQ_API_KEY": "test-key",
        "LLM_MODEL": "llama-3.1-70b-versatile"
    }):
        from src.llm.client import LLMClient
        client = LLMClient()
        
        assert client.provider == "groq"
        assert client.model == "llama-3.1-70b-versatile"

def test_llm_client_missing_key():
    """Test LLM client raises error when API key missing."""
    with patch.dict(os.environ, {"LLM_PROVIDER": "groq"}, clear=True):
        from src.llm.client import LLMClient
        
        with pytest.raises(ValueError, match="GROQ_API_KEY not found"):
            LLMClient()

def test_llm_get_info():
    """Test LLM info returns correct provider details."""
    with patch.dict(os.environ, {
        "LLM_PROVIDER": "groq",
        "GROQ_API_KEY": "test-key",
        "LLM_MODEL": "llama-3.1-70b-versatile"
    }):
        from src.llm.client import LLMClient
        client = LLMClient()
        info = client.get_info()
        
        assert info["provider"] == "groq"
        assert info["model"] == "llama-3.1-70b-versatile"
        assert info["is_free"] is True
