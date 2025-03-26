"""Base provider class for LLM implementations."""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Union
from ..config import ProviderConfig


class BaseProvider(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, config: ProviderConfig):
        self.config = config
    
    @abstractmethod
    def generate_text(self, prompt: str, max_tokens: Optional[int] = None, 
                     temperature: Optional[float] = None, **kwargs) -> str:
        """Generate text from a prompt."""
        pass
    
    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], max_tokens: Optional[int] = None,
            temperature: Optional[float] = None, **kwargs) -> Dict:
        """Generate a chat response from a list of messages."""
        pass 