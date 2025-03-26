"""Grok AI implementation for LLM provider."""
import requests
from typing import Dict, List, Optional, Union
from .base_provider import BaseProvider
from ..config import ProviderConfig


class GrokConnector(BaseProvider):
    """Connector for Grok AI API."""
    
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.api_key = config.api_key
        self.base_url = config.base_url or "https://api.grok.ai/v1"
        self.model = config.model_name or "grok-1"
        
    def _make_request(self, endpoint: str, payload: Dict) -> Dict:
        """Make a request to the Grok API."""
        url = f"{self.base_url}/{endpoint}"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        
        return response.json()
    
    def generate_text(self, prompt: str, max_tokens: Optional[int] = None, 
                     temperature: Optional[float] = None, **kwargs) -> str:
        """Generate text completion from a prompt."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "max_tokens": max_tokens or self.config.max_tokens,
            "temperature": temperature or self.config.temperature
        }
        
        # Add any additional parameters
        payload.update(kwargs)
        
        response = self._make_request("completions", payload)
        
        return response.get("choices", [{}])[0].get("text", "")
    
    def chat(self, messages: List[Dict[str, str]], max_tokens: Optional[int] = None,
            temperature: Optional[float] = None, **kwargs) -> Dict:
        """Generate a chat response from a list of messages."""
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens or self.config.max_tokens,
            "temperature": temperature or self.config.temperature
        }
        
        # Add any additional parameters
        payload.update(kwargs)
        
        response = self._make_request("chat/completions", payload)
        
        result = {
            "content": response.get("choices", [{}])[0].get("message", {}).get("content", ""),
            "model": self.model,
            "usage": response.get("usage", {})
        }
        
        return result 