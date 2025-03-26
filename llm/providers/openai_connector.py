"""OpenAI implementation for LLM provider."""
import openai
from typing import Dict, List, Optional, Union
from .base_provider import BaseProvider
from ..config import ProviderConfig


class OpenAIConnector(BaseProvider):
    """Connector for OpenAI API."""
    
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.client = openai.OpenAI(
            api_key=config.api_key,
            base_url=config.base_url
        )
        self.model = config.model_name or "gpt-4o"
        
    def generate_text(self, prompt: str, max_tokens: Optional[int] = None, 
                     temperature: Optional[float] = None, **kwargs) -> str:
        """Generate text completion from a prompt."""
        response = self.client.completions.create(
            model=self.model,
            prompt=prompt,
            max_tokens=max_tokens or self.config.max_tokens,
            temperature=temperature or self.config.temperature,
            **kwargs
        )
        return response.choices[0].text.strip()
    
    def chat(self, messages: List[Dict[str, str]], max_tokens: Optional[int] = None,
            temperature: Optional[float] = None, **kwargs) -> Dict:
        """Generate a chat response from a list of messages."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens or self.config.max_tokens,
            temperature=temperature or self.config.temperature,
            **kwargs
        )
        
        result = {
            "content": response.choices[0].message.content,
            "model": response.model,
            "usage": {
                "completion_tokens": response.usage.completion_tokens,
                "prompt_tokens": response.usage.prompt_tokens,
                "total_tokens": response.usage.total_tokens
            }
        }
        
        return result 