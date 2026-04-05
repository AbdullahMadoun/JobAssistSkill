"""
LLM Client wrapper for career assistant pipeline.

Provides a simple interface for calling LLM APIs with retry logic
and error handling.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Response from LLM API call."""
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    model: Optional[str] = None


class LLMClient:
    """
    Simple LLM client wrapper with retry logic and error handling.
    
    Supports OpenAI and Anthropic APIs via their official SDKs.
    
    Usage:
        client = LLMClient(provider="openai", model="gpt-4")
        response = client.complete([{"role": "user", "content": "Hello"}])
    """

    def __init__(
        self,
        provider: str = "openai",
        model: str = "gpt-4",
        api_key: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        timeout: int = 60,
    ):
        """
        Initialize LLM client.
        
        Args:
            provider: LLM provider ("openai" or "anthropic")
            model: Model name to use
            api_key: API key (will use env var if not provided)
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            timeout: Request timeout in seconds
        """
        self.provider = provider.lower()
        self.model = model
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        self._client = None
        self._api_key = api_key

    def _get_api_key(self) -> str:
        """Get API key from parameter or environment."""
        if self._api_key:
            return self._api_key
        
        if self.provider == "openai":
            import os
            return os.environ.get("OPENAI_API_KEY", "")
        elif self.provider == "anthropic":
            import os
            return os.environ.get("ANTHROPIC_API_KEY", "")
        return ""

    def _initialize_client(self):
        """Initialize the underlying LLM client."""
        if self._client is not None:
            return
        
        api_key = self._get_api_key()
        
        if self.provider == "openai":
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=api_key, timeout=self.timeout)
            except ImportError:
                logger.warning("OpenAI SDK not installed. Using basic HTTP client.")
                self._client = None
        elif self.provider == "anthropic":
            try:
                from anthropic import Anthropic
                self._client = Anthropic(api_key=api_key, timeout=self.timeout)
            except ImportError:
                logger.warning("Anthropic SDK not installed. Using basic HTTP client.")
                self._client = None
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def _make_openai_request(self, messages: List[Dict], system: str = "") -> LLMResponse:
        """Make request to OpenAI API."""
        self._initialize_client()
        
        try:
            from openai import OpenAI
            if isinstance(self._client, OpenAI):
                params = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.0,
                }
                if system:
                    params["messages"] = [{"role": "system", "content": system}] + messages
                
                response = self._client.chat.completions.create(**params)
                
                return LLMResponse(
                    success=True,
                    content=response.choices[0].message.content,
                    usage={
                        "prompt_tokens": response.usage.prompt_tokens if hasattr(response.usage, "prompt_tokens") else 0,
                        "completion_tokens": response.usage.completion_tokens if hasattr(response.usage, "completion_tokens") else 0,
                        "total_tokens": response.usage.total_tokens if hasattr(response.usage, "total_tokens") else 0,
                    },
                    model=response.model,
                )
        except Exception as e:
            return LLMResponse(success=False, error=str(e))
        
        return LLMResponse(success=False, error="OpenAI client not properly initialized")

    def _make_anthropic_request(self, messages: List[Dict], system: str = "") -> LLMResponse:
        """Make request to Anthropic API."""
        self._initialize_client()
        
        try:
            from anthropic import Anthropic
            if isinstance(self._client, Anthropic):
                # Convert messages format for Anthropic
                anthropic_messages = []
                for msg in messages:
                    if msg["role"] == "system":
                        continue
                    anthropic_messages.append({
                        "role": msg["role"],
                        "content": msg["content"],
                    })
                
                params = {
                    "model": self.model,
                    "messages": anthropic_messages,
                    "max_tokens": 4096,
                }
                if system:
                    params["system"] = system
                
                response = self._client.messages.create(**params)
                
                return LLMResponse(
                    success=True,
                    content=response.content[0].text if response.content else "",
                    usage={
                        "input_tokens": response.usage.input_tokens if hasattr(response.usage, "input_tokens") else 0,
                        "output_tokens": response.usage.output_tokens if hasattr(response.usage, "output_tokens") else 0,
                    },
                    model=response.model,
                )
        except Exception as e:
            return LLMResponse(success=False, error=str(e))
        
        return LLMResponse(success=False, error="Anthropic client not properly initialized")

    def complete(
        self,
        messages: List[Dict[str, str]],
        system: str = "",
        json_mode: bool = False,
    ) -> LLMResponse:
        """
        Send a completion request to the LLM.
        
        Args:
            messages: List of message dicts with "role" and "content"
            system: Optional system prompt
            json_mode: If True, request JSON response format
            
        Returns:
            LLMResponse with the model's reply
        """
        for attempt in range(self.max_retries):
            try:
                if self.provider == "openai":
                    response = self._make_openai_request(messages, system)
                elif self.provider == "anthropic":
                    response = self._make_anthropic_request(messages, system)
                else:
                    return LLMResponse(success=False, error=f"Unknown provider: {self.provider}")
                
                if response.success:
                    return response
                
                if attempt < self.max_retries - 1:
                    logger.warning(f"LLM request failed (attempt {attempt + 1}): {response.error}")
                    time.sleep(self.retry_delay * (attempt + 1))
                    
            except Exception as e:
                if attempt < self.max_retries - 1:
                    logger.warning(f"LLM request exception (attempt {attempt + 1}): {e}")
                    time.sleep(self.retry_delay * (attempt + 1))
                else:
                    return LLMResponse(success=False, error=str(e))
        
        return LLMResponse(success=False, error="Max retries exceeded")

    def complete_with_json(
        self,
        messages: List[Dict[str, str]],
        system: str = "",
    ) -> LLMResponse:
        """
        Send a completion request expecting JSON response.
        
        Tries to parse the response as JSON and returns error if invalid.
        
        Args:
            messages: List of message dicts with "role" and "content"
            system: Optional system prompt
            
        Returns:
            LLMResponse with parsed JSON content
        """
        response = self.complete(messages, system)
        
        if not response.success:
            return response
        
        try:
            # Try to extract JSON from the response
            content = response.content.strip()
            
            # Handle JSON wrapped in markdown code blocks
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]
            
            if content.endswith("```"):
                content = content[:-3]
            
            content = content.strip()
            parsed = json.loads(content)
            
            return LLMResponse(
                success=True,
                content=json.dumps(parsed),
                usage=response.usage,
                model=response.model,
            )
        except json.JSONDecodeError as e:
            return LLMResponse(
                success=False,
                error=f"Failed to parse JSON response: {e}",
                content=response.content,
            )


def get_default_client() -> LLMClient:
    """Get a default LLM client instance."""
    return LLMClient(provider="openai", model="gpt-4o")


_default_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get singleton default LLM client."""
    global _default_client
    if _default_client is None:
        _default_client = get_default_client()
    return _default_client
