"""
Main connector module for LLM integration.
"""
from typing import Dict, List, Optional, Union
from .config import LLMConfig


class LLMConnector:
    """Main connector class for interacting with LLM models."""
    
    def __init__(self, config: Optional[LLMConfig] = None):
        """Initialize with optional configuration."""
        self.config = config or LLMConfig()
        self.provider_instances = {}
    
    def get_provider(self, provider_name: str):
        """Get or create an instance of the specified provider."""
        if provider_name not in self.provider_instances:
            # Lazy-load provider implementations
            provider_config = self.config.get_provider_config(provider_name)
            if not provider_config:
                raise ValueError(f"Provider '{provider_name}' not configured")
            
            if provider_name == 'openai':
                from .providers.openai_connector import OpenAIConnector
                self.provider_instances[provider_name] = OpenAIConnector(provider_config)
            elif provider_name == 'anthropic':
                from .providers.anthropic_connector import AnthropicConnector
                self.provider_instances[provider_name] = AnthropicConnector(provider_config)
            elif provider_name == 'ollama':
                from .providers.ollama_connector import OllamaConnector
                self.provider_instances[provider_name] = OllamaConnector(provider_config)
            elif provider_name == 'grok':
                from .providers.grok_connector import GrokConnector
                self.provider_instances[provider_name] = GrokConnector(provider_config)
            elif provider_name == 'bedrock':
                from .providers.bedrock_connector import BedrockConnector
                self.provider_instances[provider_name] = BedrockConnector(provider_config)
            else:
                from .providers.generic_connector import GenericConnector
                self.provider_instances[provider_name] = GenericConnector(provider_config)
                
        return self.provider_instances[provider_name]
    
    def get_available_providers(self) -> List[str]:
        """Get a list of available providers based on configuration."""
        return self.config.get_available_providers()
    
    def generate_text(self, 
                     prompt: str, 
                     provider: Optional[str] = None,
                     max_tokens: Optional[int] = None,
                     temperature: Optional[float] = None,
                     **kwargs) -> str:
        """
        Generate text from a prompt using the specified provider.
        
        Args:
            prompt: The text prompt to send to the model
            provider: The LLM provider to use (if None, uses the first available)
            max_tokens: Maximum tokens in the response
            temperature: Temperature for generation
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Generated text response
        """
        if not provider:
            available_providers = self.get_available_providers()
            if not available_providers:
                raise ValueError("No LLM providers configured")
            provider = available_providers[0]
            
        provider_instance = self.get_provider(provider)
        return provider_instance.generate_text(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        )
    
    def chat(self,
            messages: List[Dict[str, str]],
            provider: Optional[str] = None,
            max_tokens: Optional[int] = None,
            temperature: Optional[float] = None,
            **kwargs) -> Dict:
        """
        Generate a chat response from a list of messages.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            provider: The LLM provider to use (if None, uses the first available)
            max_tokens: Maximum tokens in the response
            temperature: Temperature for generation
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Response dictionary containing generated text and metadata
        """
        if not provider:
            available_providers = self.get_available_providers()
            if not available_providers:
                raise ValueError("No LLM providers configured")
            provider = available_providers[0]
            
        provider_instance = self.get_provider(provider)
        return provider_instance.chat(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        ) 