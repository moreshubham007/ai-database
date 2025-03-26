"""Generic REST API implementation for other LLM providers."""
import requests
from typing import Dict, List, Optional, Union
from .base_provider import BaseProvider
from ..config import ProviderConfig


class GenericConnector(BaseProvider):
    """Connector for generic REST API LLM endpoints."""
    
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.api_key = config.api_key
        self.base_url = config.base_url 
        self.model = config.model_name
        
    def _make_request(self, endpoint: str, payload: Dict) -> Dict:
        """Make a request to the API."""
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
        
        # Add any additional parameters from config
        if self.config.additional_params:
            payload.update(self.config.additional_params)
            
        # Add any runtime parameters
        payload.update(kwargs)
        
        # The endpoint path is configurable through additional_params
        endpoint = self.config.additional_params.get("completion_endpoint", "completions")
        
        response = self._make_request(endpoint, payload)
        
        # The response parsing is configurable through additional_params
        text_path = self.config.additional_params.get("text_path", "choices.0.text")
        
        # Parse nested path
        parts = text_path.split('.')
        value = response
        for part in parts:
            if part.isdigit():
                part = int(part)
            try:
                value = value[part]
            except (KeyError, IndexError, TypeError):
                return ""
                
        return value
    
    def chat(self, messages: List[Dict[str, str]], max_tokens: Optional[int] = None,
            temperature: Optional[float] = None, **kwargs) -> Dict:
        """Generate a chat response from a list of messages."""
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens or self.config.max_tokens,
            "temperature": temperature or self.config.temperature
        }
        
        # Add any additional parameters from config
        if self.config.additional_params:
            payload.update(self.config.additional_params)
            
        # Add any runtime parameters
        payload.update(kwargs)
        
        # The endpoint path is configurable through additional_params
        endpoint = self.config.additional_params.get("chat_endpoint", "chat/completions")
        
        response = self._make_request(endpoint, payload)
        
        # The response parsing is configurable through additional_params
        content_path = self.config.additional_params.get("content_path", "choices.0.message.content")
        
        # Parse nested path for content
        parts = content_path.split('.')
        content = response
        for part in parts:
            if part.isdigit():
                part = int(part)
            try:
                content = content[part]
            except (KeyError, IndexError, TypeError):
                content = ""
                break
                
        result = {
            "content": content,
            "model": self.model,
            "usage": response.get("usage", {})
        }
        
        return result 