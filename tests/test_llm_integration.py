"""
Integration tests for LLM client with actual API calls.

These tests require a valid GROQ_API_KEY environment variable.
Run with: pytest tests/test_llm_integration.py -v -s
"""

import os
import pytest
from unittest.mock import patch


def has_groq_api_key():
    """Check if GROQ_API_KEY is available."""
    return bool(os.getenv("GROQ_API_KEY"))


@pytest.mark.skipif(not has_groq_api_key(), reason="GROQ_API_KEY not set")
class TestLLMIntegration:
    """Integration tests that make actual API calls to Groq."""
    
    def test_llm_client_real_initialization(self):
        """Test LLM client initializes with real Groq API."""
        from src.llm.client import LLMClient
        
        client = LLMClient()
        
        assert client.provider == "groq"
        assert client.client is not None
        assert hasattr(client.client, 'chat')
    
    def test_llm_chat_completion_real(self):
        """Test actual chat completion with Groq API."""
        from src.llm.client import LLMClient
        
        client = LLMClient()
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant. Respond briefly."},
            {"role": "user", "content": "What is 2 + 2? Answer with just the number."}
        ]
        
        response = client.chat_completion(
            messages=messages,
            temperature=0.0,
            max_tokens=10
        )
        
        # Verify response structure
        assert "content" in response
        assert "model" in response
        assert "usage" in response
        
        # Verify usage stats
        assert response["usage"]["prompt_tokens"] > 0
        assert response["usage"]["completion_tokens"] > 0
        assert response["usage"]["total_tokens"] > 0
        
        # Verify the response contains "4"
        assert "4" in response["content"]
        
        print(f"\nLLM Response: {response['content']}")
        print(f"Model: {response['model']}")
        print(f"Tokens used: {response['usage']['total_tokens']}")
    
    def test_llm_json_mode(self):
        """Test JSON mode response from Groq API."""
        from src.llm.client import LLMClient
        import json
        
        client = LLMClient()
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant that responds in JSON format."},
            {"role": "user", "content": "Return a JSON object with keys 'status' set to 'ok' and 'value' set to 42."}
        ]
        
        response = client.chat_completion(
            messages=messages,
            temperature=0.0,
            max_tokens=50,
            json_mode=True
        )
        
        # Verify response is valid JSON
        content = response["content"]
        parsed = json.loads(content)
        
        assert "status" in parsed or "value" in parsed
        print(f"\nJSON Response: {parsed}")
    
    def test_llm_risk_analysis_prompt(self):
        """Test a realistic risk analysis prompt."""
        from src.llm.client import LLMClient
        
        client = LLMClient()
        
        messages = [
            {
                "role": "system", 
                "content": """You are a financial risk analyst. Analyze the following SEC filing excerpt 
                and provide a risk score from 1-10 where 10 is highest risk. 
                Respond with just the number."""
            },
            {
                "role": "user", 
                "content": """The company faces significant litigation risks related to ongoing 
                patent disputes. Additionally, there are material weaknesses in internal controls 
                that could affect financial reporting accuracy."""
            }
        ]
        
        response = client.chat_completion(
            messages=messages,
            temperature=0.0,
            max_tokens=10
        )
        
        content = response["content"].strip()
        
        # Should return a number between 1-10
        # Extract first number found
        import re
        numbers = re.findall(r'\d+', content)
        assert len(numbers) > 0, f"Expected a number in response: {content}"
        
        risk_score = int(numbers[0])
        assert 1 <= risk_score <= 10, f"Risk score {risk_score} out of range"
        
        print(f"\nRisk Analysis Response: {content}")
        print(f"Extracted Risk Score: {risk_score}")
    
    def test_llm_get_info_real(self):
        """Test get_info with real client."""
        from src.llm.client import LLMClient
        
        client = LLMClient()
        info = client.get_info()
        
        assert info["provider"] == "groq"
        assert "llama" in info["model"].lower() or "mixtral" in info["model"].lower() or "versatile" in info["model"].lower()
        assert info["is_free"] is True
        
        print(f"\nLLM Info: {info}")


@pytest.mark.skipif(not has_groq_api_key(), reason="GROQ_API_KEY not set")
class TestLLMErrorHandling:
    """Test error handling with real API."""
    
    def test_llm_handles_empty_messages(self):
        """Test handling of empty messages list."""
        from src.llm.client import LLMClient
        
        client = LLMClient()
        
        with pytest.raises(Exception):
            client.chat_completion(messages=[], max_tokens=10)
    
    def test_llm_handles_invalid_model(self):
        """Test handling of invalid model name."""
        import os
        
        original_model = os.environ.get("LLM_MODEL")
        
        try:
            os.environ["LLM_MODEL"] = "invalid-model-name"
            
            from importlib import reload
            import src.llm.client as llm_module
            reload(llm_module)
            
            client = llm_module.LLMClient()
            
            with pytest.raises(Exception):
                client.chat_completion(
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=10
                )
        finally:
            if original_model:
                os.environ["LLM_MODEL"] = original_model
            elif "LLM_MODEL" in os.environ:
                del os.environ["LLM_MODEL"]
