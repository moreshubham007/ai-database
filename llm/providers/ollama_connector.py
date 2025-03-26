"""Ollama implementation for local LLM provider."""
import requests
import json
from typing import Dict, List, Optional, Union
from .base_provider import BaseProvider
from ..config import ProviderConfig


class OllamaConnector(BaseProvider):
    """Connector for Ollama local API."""
    
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.base_url = config.base_url or "http://localhost:11434"
        self.model = config.model_name or "llama3"
        
    def generate_text(self, prompt: str, max_tokens: Optional[int] = None, 
                     temperature: Optional[float] = None, **kwargs) -> str:
        """Generate text completion from a prompt."""
        url = f"{self.base_url}/api/generate"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }
        
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature
            
        # Add any additional parameters
        payload.update(kwargs)
        
        response = requests.post(url, json=payload)
        response.raise_for_status()
        
        return response.json().get("response", "")
    
    def chat(self, messages: List[Dict[str, str]], max_tokens: Optional[int] = None,
            temperature: Optional[float] = None, **kwargs) -> Dict:
        """Generate a chat response from a list of messages."""
        url = f"{self.base_url}/api/chat"
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False
        }
        
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if temperature is not None:
            payload["temperature"] = temperature
            
        # Add any additional parameters
        payload.update(kwargs)
        
        response = requests.post(url, json=payload)
        response.raise_for_status()
        response_data = response.json()
        
        result = {
            "content": response_data.get("message", {}).get("content", ""),
            "model": self.model,
            # Ollama doesn't provide detailed token usage information
            "usage": {}
        }
        
        return result 