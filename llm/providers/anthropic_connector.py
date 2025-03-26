"""Anthropic Claude implementation for LLM provider."""
import anthropic
from typing import Dict, List, Optional, Union
from .base_provider import BaseProvider
from ..config import ProviderConfig


class AnthropicConnector(BaseProvider):
    """Connector for Anthropic Claude API."""
    
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        # Initialize client with base_url if provided
        client_kwargs = {"api_key": config.api_key}
        if config.base_url:
            client_kwargs["base_url"] = config.base_url
        self.client = anthropic.Anthropic(**client_kwargs)
        self.model = config.model_name or "claude-3-opus-20240229"
        
    def generate_text(self, prompt: str, max_tokens: Optional[int] = None, 
                     temperature: Optional[float] = None, **kwargs) -> str:
        """Generate text completion from a prompt."""
        # Anthropic requires using the chat endpoint even for simple completions
        response = self.client.messages.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens or self.config.max_tokens,
            temperature=temperature or self.config.temperature,
            **kwargs
        )
        return response.content[0].text
    
    def chat(self, messages: List[Dict[str, str]], max_tokens: Optional[int] = None,
            temperature: Optional[float] = None, **kwargs) -> Dict:
        """Generate a chat response from a list of messages."""
        # Convert messages to Anthropic format if needed
        anthropic_messages = []
        for msg in messages:
            # Map OpenAI roles to Anthropic roles
            role = msg["role"]
            if role == "system":
                # For system messages in Anthropic, we'll add them as part of the first user message
                continue
            elif role == "assistant":
                role = "assistant"
            else:
                role = "user"
            
            anthropic_messages.append({"role": role, "content": msg["content"]})
        
        # Add system message as a parameter if present
        system_message = next((m["content"] for m in messages if m["role"] == "system"), None)
        
        response = self.client.messages.create(
            model=self.model,
            messages=anthropic_messages,
            system=system_message,
            max_tokens=max_tokens or self.config.max_tokens,
            temperature=temperature or self.config.temperature,
            **kwargs
        )
        
        result = {
            "content": response.content[0].text,
            "model": response.model,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens
            }
        }
        
        return result 