import os
from groq import Groq
from typing import Dict, Optional

class LLMClient:
    """Unified LLM client supporting Groq (free) and other providers."""
    
    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "groq")
        self.model = os.getenv("LLM_MODEL", "llama-3.1-70b-versatile")
        
        if self.provider == "groq":
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                raise ValueError("GROQ_API_KEY not found in environment")
            self.client = Groq(api_key=api_key)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")
    
    def chat_completion(
        self,
        messages: list,
        temperature: float = 0.3,
        max_tokens: int = 1000,
        json_mode: bool = False
    ) -> Dict:
        """Generate chat completion with unified interface."""
        
        if self.provider == "groq":
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            
            response = self.client.chat.completions.create(**kwargs)
            
            return {
                "content": response.choices[0].message.content,
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }
        
        raise ValueError(f"Provider {self.provider} not implemented")
    
    def get_info(self) -> Dict:
        """Get LLM provider information."""
        return {
            "provider": self.provider,
            "model": self.model,
            "is_free": self.provider == "groq"
        }
