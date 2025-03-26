"""Utility functions for LLM module."""
import time
from typing import Dict, List, Optional, Callable
from functools import wraps


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0, 
                      max_delay: float = 10.0):
    """
    Retry decorator with exponential backoff for API calls.
    
    Args:
        max_retries: Maximum number of retries
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = base_delay
            for retry in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if retry == max_retries:
                        raise
                    
                    # Calculate backoff delay
                    sleep_time = min(delay * (2 ** retry), max_delay)
                    time.sleep(sleep_time)
            
            # This should never happen
            raise RuntimeError("Unexpected error in retry_with_backoff")
        return wrapper
    return decorator


def estimate_tokens(text: str) -> int:
    """
    Roughly estimate the number of tokens in a text.
    
    This is a very simple approximation based on whitespace tokenization
    that can be used when you don't want to load a full tokenizer.
    
    Args:
        text: Input text
        
    Returns:
        Estimated token count
    """
    # Very rough approximation: words + punctuation
    words = text.split()
    # Add 1 token for approximately every 3 punctuation marks
    punctuation = sum(c in '.,;:!?"\'()[]{}' for c in text) // 3
    return len(words) + punctuation 


def check_library_versions():
    """Check if required libraries are installed with compatible versions."""
    try:
        import importlib.metadata
        
        # Check OpenAI version
        try:
            openai_version = importlib.metadata.version('openai')
            if not openai_version.startswith('1.'):
                print(f"Warning: OpenAI version {openai_version} may not be compatible. Version 1.x is recommended.")
        except importlib.metadata.PackageNotFoundError:
            print("Warning: OpenAI package not found.")
        
        # Check Anthropic version
        try:
            anthropic_version = importlib.metadata.version('anthropic')
            anthropic_version_parts = [int(p) for p in anthropic_version.split('.')]
            if anthropic_version_parts[0] < 0 or (anthropic_version_parts[0] == 0 and anthropic_version_parts[1] < 5):
                print(f"Warning: Anthropic version {anthropic_version} may not be compatible. Version 0.5.0+ is recommended.")
        except (importlib.metadata.PackageNotFoundError, ValueError, IndexError):
            print("Warning: Anthropic package not found or version format unexpected.")
            
    except ImportError:
        # importlib.metadata is Python 3.8+
        print("Warning: Cannot check package versions. Python 3.8+ recommended.") 