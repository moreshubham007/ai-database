"""
Configuration for LLM connections.
"""
import os
from dataclasses import dataclass
from typing import Dict, Optional
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@dataclass
class ProviderConfig:
    """Configuration for a specific LLM provider."""
    api_key: str
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    timeout: int = 30
    max_tokens: int = 1000
    temperature: float = 0.7
    additional_params: Dict = None

    def __post_init__(self):
        if self.additional_params is None:
            self.additional_params = {}


class LLMConfig:
    """Configuration manager for LLM connections."""
    
    def __init__(self):
        """Initialize configuration manager."""
        self.providers = {}
        
        # Load from environment variables
        self._load_from_env()
        
        # Try to load Bedrock config from database if MongoDB is available
        try:
            from flask import current_app
            if hasattr(current_app, 'mongo'):
                bedrock_config = current_app.mongo.db.settings.find_one({'setting_type': 'bedrock_config'})
                if bedrock_config:
                    # Add Bedrock provider
                    self.providers['bedrock'] = ProviderConfig(
                        api_key=f"{bedrock_config.get('aws_access_key')}:{bedrock_config.get('aws_secret_key')}",
                        base_url=bedrock_config.get('aws_region', 'us-east-1'),
                        model_name=bedrock_config.get('model_id', 'amazon.titan-text-express-v1'),
                        max_tokens=1000,
                        temperature=0.7
                    )
        except Exception as e:
            print(f"Error loading Bedrock config from database: {str(e)}")
    
    def _load_from_env(self):
        """Load configuration from environment variables."""
        # OpenAI configuration
        if os.environ.get('OPENAI_API_KEY'):
            self.providers['openai'] = ProviderConfig(
                api_key=os.environ.get('OPENAI_API_KEY'),
                base_url=os.environ.get('OPENAI_BASE_URL'),
                model_name=os.environ.get('OPENAI_MODEL_NAME', 'gpt-4o')
            )
        
        # Anthropic configuration
        if os.environ.get('ANTHROPIC_API_KEY'):
            self.providers['anthropic'] = ProviderConfig(
                api_key=os.environ.get('ANTHROPIC_API_KEY'),
                model_name=os.environ.get('ANTHROPIC_MODEL_NAME', 'claude-3-opus-20240229')
            )
        
        # Ollama configuration (no API key needed, just endpoint)
        if os.environ.get('OLLAMA_BASE_URL'):
            self.providers['ollama'] = ProviderConfig(
                api_key="",  # Ollama doesn't need an API key for local deployments
                base_url=os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434'),
                model_name=os.environ.get('OLLAMA_MODEL_NAME', 'llama3')
            )
            
        # Grok configuration
        if os.environ.get('GROK_API_KEY'):
            self.providers['grok'] = ProviderConfig(
                api_key=os.environ.get('GROK_API_KEY'),
                base_url=os.environ.get('GROK_BASE_URL'),
                model_name=os.environ.get('GROK_MODEL_NAME', 'grok-1')
            )
    
    def get_provider_config(self, provider_name: str) -> Optional[ProviderConfig]:
        """Get configuration for a provider."""
        return self.providers.get(provider_name)
    
    def get_available_providers(self) -> list:
        """Get a list of available provider names."""
        return list(self.providers.keys()) 