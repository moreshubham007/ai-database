"""
Connector for Amazon Bedrock API.
"""
import boto3
import json
import logging
from botocore.config import Config
from botocore.exceptions import ClientError, BotoCoreError
from typing import List, Dict, Any, Union, Optional

from .base_provider import BaseProvider
from ..config import ProviderConfig

# Set up logging
logger = logging.getLogger(__name__)

class BedrockConnector(BaseProvider):
    """Connector for Amazon Bedrock API."""
    
    def __init__(self, config: ProviderConfig):
        """Initialize the Amazon Bedrock connector.
        
        Args:
            config: Configuration for the provider
        """
        super().__init__(config)
        
        # Get configuration parameters
        self.model_id = config.model_name or "amazon.titan-text-express-v1"
        self.region = config.base_url or "us-east-1"  # Default to us-east-1 if not specified
        self.max_tokens = config.max_tokens or 1000
        self.temperature = config.temperature or 0.7
        
        try:
            # Initialize Bedrock client with proper credentials
            boto_config = Config(
                region_name=self.region,
                signature_version="v4",
                retries={"max_attempts": 10, "mode": "standard"}
            )
            
            # Get credentials from config or environment
            # For Bedrock, the API key is actually the AWS access key ID
            if config.api_key and ":" in config.api_key:
                # Format: "ACCESS_KEY:SECRET_KEY"
                access_key, secret_key = config.api_key.split(":", 1)
                self.bedrock_runtime = boto3.client(
                    service_name="bedrock-runtime",
                    config=boto_config,
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key
                )
                logger.info(f"Initialized Bedrock runtime client with explicit credentials in region {self.region}")
                
                # We don't need this service client for runtime operations
                # Only create it if needed for listing models or other operations
                # self.bedrock = boto3.client(
                #     service_name="bedrock",
                #     config=boto_config,
                #     aws_access_key_id=access_key,
                #     aws_secret_access_key=secret_key
                # )
            else:
                # Fall back to default credential provider chain
                self.bedrock_runtime = boto3.client(
                    service_name="bedrock-runtime",
                    config=boto_config
                )
                logger.info(f"Initialized Bedrock runtime client with environment credentials in region {self.region}")
                
            logger.info(f"Using model: {self.model_id}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock client: {str(e)}")
            print(f"Failed to initialize Bedrock client: {str(e)}")
            self.bedrock_runtime = None
    
    def generate_text(self, prompt: str, max_tokens: Optional[int] = None, temperature: Optional[float] = None, **kwargs) -> str:
        """Generate text using the Amazon Bedrock service.
        
        Args:
            prompt: The text prompt to send to the model
            max_tokens: Maximum tokens in the response (overrides config)
            temperature: Temperature for generation (overrides config)
            **kwargs: Additional parameters for the model
            
        Returns:
            Generated text response
        """
        if not self.bedrock_runtime:
            return "Error: Bedrock client not initialized"
        
        try:
            # Determine the model ID from the configuration
            model_id = self.model_id
            
            # Set proper parameters based on the model type
            body_params = {}
            
            # Extract numeric values to ensure they're JSON serializable
            max_tokens_val = int(max_tokens if max_tokens is not None else self.max_tokens)
            temp_val = float(temperature if temperature is not None else self.temperature)
            
            # Handle different model formats - each model family has different parameters
            if "claude" in model_id.lower():
                # Anthropic Claude models
                body_params = {
                    "prompt": f"\n\nHuman: {prompt}\n\nAssistant:",
                    "max_tokens_to_sample": max_tokens_val,
                    "temperature": temp_val,
                    "stop_sequences": ["\n\nHuman:"]
                }
            elif "titan" in model_id.lower():
                # Amazon Titan models
                body_params = {
                    "inputText": prompt,
                    "textGenerationConfig": {
                        "maxTokenCount": max_tokens_val,
                        "temperature": temp_val,
                        "stopSequences": []
                    }
                }
            elif "llama" in model_id.lower() or "meta" in model_id.lower():
                # Meta Llama models
                body_params = {
                    "prompt": prompt,
                    "max_gen_len": max_tokens_val,
                    "temperature": temp_val
                }
            elif "mistral" in model_id.lower():
                # Mistral models
                body_params = {
                    "prompt": prompt,
                    "max_tokens": max_tokens_val,
                    "temperature": temp_val
                }
            else:
                # Generic fallback
                body_params = {
                    "prompt": prompt,
                    "max_tokens": max_tokens_val,
                    "temperature": temp_val
                }
            
            # Add any additional parameters
            for key, value in kwargs.items():
                if key not in ["model_id", "prompt", "max_tokens", "temperature"]:
                    body_params[key] = value
            
            # Convert to JSON - this is where the error was happening
            body = json.dumps(body_params)
            
            # Call the Bedrock Runtime service
            response = self.bedrock_runtime.invoke_model(
                modelId=model_id,
                body=body
            )
            
            # Process the response based on the model
            response_body = json.loads(response.get('body').read())
            
            if "claude" in model_id.lower():
                return response_body.get('completion', '')
            elif "titan" in model_id.lower():
                return response_body.get('results', [{}])[0].get('outputText', '')
            elif "llama" in model_id.lower() or "meta" in model_id.lower():
                return response_body.get('generation', '')
            elif "mistral" in model_id.lower():
                return response_body.get('outputs', [{}])[0].get('text', '')
            else:
                # Try to find any text field in the response
                for key in ['text', 'content', 'output', 'completion', 'response', 'generated_text']:
                    if key in response_body:
                        return response_body[key]
                return str(response_body)  # Last resort
                
        except Exception as e:
            error_msg = f"Error in Bedrock text generation: {str(e)}"
            logger.error(error_msg)
            return f"Error: {error_msg}"
    
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> Dict:
        """Generate a response to a conversation using Amazon Bedrock.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            **kwargs: Additional parameters
            
        Returns:
            Dictionary containing the response and metadata
        """
        try:
            # Most Bedrock models don't have a native chat format, so we'll convert
            # the messages to a prompt string
            
            # Handle system message separately for models that support it
            system_message = ""
            prompt_parts = []
            
            for message in messages:
                role = message.get("role", "user")
                content = message.get("content", "")
                
                if role == "system" and "claude" in self.model_id.lower():
                    system_message = content
                elif role == "user":
                    prompt_parts.append(f"Human: {content}")
                elif role == "assistant":
                    prompt_parts.append(f"Assistant: {content}")
                else:
                    # For other roles, just include the content
                    prompt_parts.append(content)
            
            # Special handling for Anthropic models which have a specific format
            if "claude" in self.model_id.lower():
                # Start with system message if provided
                if system_message:
                    prompt = f"\n\nHuman: <system>{system_message}</system>\n\n"
                    # Add the conversation, removing the last assistant message
                    conversation = "\n\n".join(prompt_parts[:-1] if prompt_parts[-1].startswith("Assistant:") else prompt_parts)
                    prompt += f"{conversation}\n\nAssistant:"
                else:
                    # Just format the conversation normally
                    conversation = "\n\n".join(prompt_parts)
                    prompt = f"\n\n{conversation}\n\nAssistant:"
            else:
                # For other models, just concatenate the messages
                prompt = "\n".join(prompt_parts)
                if not prompt_parts[-1].startswith("Assistant:"):
                    prompt += "\nAssistant:"
            
            # Generate the response
            response_text = self.generate_text(prompt, **kwargs)
            
            # Return in a format compatible with other providers
            return {
                "content": response_text,
                "model": self.model_id,
                "usage": {
                    # Bedrock doesn't provide token counts in a standard way
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0
                }
            }
        
        except Exception as e:
            error_msg = f"Error in Bedrock chat: {str(e)}"
            logger.error(error_msg)
            return {
                "content": f"Error: {error_msg}",
                "model": self.model_id,
                "usage": {}
            } 