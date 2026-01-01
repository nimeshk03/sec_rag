import os
import sys
import pytest
from unittest.mock import patch, MagicMock

@pytest.fixture(autouse=True)
def cleanup_llm_module():
    """Clean up LLM module after each test to avoid polluting other tests."""
    yield
    # Remove the module from cache so it gets reimported fresh
    modules_to_remove = [key for key in sys.modules if key.startswith('src.llm')]
    for mod in modules_to_remove:
        del sys.modules[mod]

def test_llm_client_initialization():
    """Test LLM client can be initialized with Groq."""
    with patch.dict(os.environ, {
        "LLM_PROVIDER": "groq",
        "GROQ_API_KEY": "test-key",
        "LLM_MODEL": "llama-3.3-70b-versatile"
    }):
        with patch('groq.Groq') as mock_groq:
            mock_groq.return_value = MagicMock()
            
            # Import fresh to pick up mocked Groq
            import importlib
            import src.llm.client as llm_module
            importlib.reload(llm_module)
            
            client = llm_module.LLMClient()
            
            assert client.provider == "groq"
            assert client.model == "llama-3.3-70b-versatile"
            mock_groq.assert_called_once_with(api_key="test-key")

def test_llm_client_missing_key():
    """Test LLM client raises error when API key missing."""
    # Save original env
    original_key = os.environ.get("GROQ_API_KEY")
    
    try:
        # Remove the key
        if "GROQ_API_KEY" in os.environ:
            del os.environ["GROQ_API_KEY"]
        os.environ["LLM_PROVIDER"] = "groq"
        
        with patch('groq.Groq') as mock_groq:
            import importlib
            import src.llm.client as llm_module
            importlib.reload(llm_module)
            
            with pytest.raises(ValueError, match="GROQ_API_KEY not found"):
                llm_module.LLMClient()
    finally:
        # Restore original env
        if original_key:
            os.environ["GROQ_API_KEY"] = original_key

def test_llm_get_info():
    """Test LLM info returns correct provider details."""
    with patch.dict(os.environ, {
        "LLM_PROVIDER": "groq",
        "GROQ_API_KEY": "test-key",
        "LLM_MODEL": "llama-3.3-70b-versatile"
    }):
        with patch('groq.Groq') as mock_groq:
            mock_groq.return_value = MagicMock()
            
            import importlib
            import src.llm.client as llm_module
            importlib.reload(llm_module)
            
            client = llm_module.LLMClient()
            info = client.get_info()
            
            assert info["provider"] == "groq"
            assert info["model"] == "llama-3.3-70b-versatile"
            assert info["is_free"] is True
