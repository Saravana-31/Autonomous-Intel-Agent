"""Ollama LLM provider via OpenAI-compatible API."""

import os
import json
import logging
import requests
from typing import Dict, Any

from .base import BaseLLM

logger = logging.getLogger(__name__)


class OllamaLLM(BaseLLM):
    """Ollama provider using OpenAI-compatible chat API.
    
    Connects to a remote or local Ollama instance via HTTP.
    Configurable via environment variables:
    - OLLAMA_BASE_URL: Base URL (default: http://localhost:11434)
    - OLLAMA_MODEL: Model name (default: llama3.1)
    - OLLAMA_TIMEOUT: Request timeout in seconds (default: 180)
    """

    def __init__(self):
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        self.model = os.getenv("OLLAMA_MODEL", "llama3.1")
        self.timeout = int(os.getenv("OLLAMA_TIMEOUT", "180"))
        self._available = None

    def _chat_endpoint(self) -> str:
        return f"{self.base_url}/v1/chat/completions"

    def _models_endpoint(self) -> str:
        return f"{self.base_url}/v1/models"

    def is_available(self) -> bool:
        """Check if Ollama is reachable and healthy."""
        try:
            resp = requests.get(self._models_endpoint(), timeout=10)
            available = resp.status_code == 200
            if available != self._available:
                self._available = available
                status = "available" if available else f"unhealthy (HTTP {resp.status_code})"
                logger.info(f"Ollama health check: {status}")
            return available
        except Exception as e:
            if self._available is not False:
                logger.debug(f"Ollama unreachable: {e}")
                self._available = False
            return False

    def get_name(self) -> str:
        return "Ollama"

    def extract(self, prompt: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data using Ollama.
        
        Args:
            prompt: Extraction prompt with mandatory field instructions
            schema: Expected schema (for reference)
            
        Returns:
            Parsed JSON response from Ollama
            
        Raises:
            RuntimeError: If request fails or response is invalid JSON
        """
        if not self.is_available():
            raise RuntimeError("Ollama is not available")

        # Enforce JSON-only output with envelope
        from json_validator import JSONValidator
        json_prompt = JSONValidator.build_json_prompt(prompt, use_envelope=True)
        
        # Enhanced system prompt with strict JSON requirements
        strict_system = """You MUST output valid JSON.
Do not truncate.
Do not stop early.
Do not use single quotes.
Wrap response in: {"status": "ok", "profile": {...}}
Complete all fields. If missing, use "not_found"."""
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": strict_system},
                {"role": "user", "content": json_prompt}
            ],
            "temperature": 0.2,  # Slightly higher for better completion
            "stream": False,
            "format": "json",  # Force JSON mode
            "options": {
                "num_predict": 1200  # Max tokens to prevent truncation
            }
        }

        try:
            logger.debug(f"Sending extraction request to Ollama ({self.model})")
            resp = requests.post(
                self._chat_endpoint(),
                json=payload,
                timeout=self.timeout  # Use configured timeout (default 180s)
            )
            resp.raise_for_status()

            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                raise RuntimeError("Empty response from Ollama")

            content = choices[0].get("message", {}).get("content", "")
            if not content:
                raise RuntimeError("No content in Ollama response")
            
            # Check completeness before parsing
            is_complete, issue = JSONValidator.check_completeness(content)
            if not is_complete:
                logger.warning(f"Ollama output incomplete: {issue}. Attempting retry...")
                # Retry once with completion instruction
                retry_prompt = f"""The previous JSON was truncated: {content[:200]}...
Return the FULL corrected JSON only. Complete all fields."""
                retry_payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": strict_system},
                        {"role": "user", "content": json_prompt},
                        {"role": "assistant", "content": content},
                        {"role": "user", "content": retry_prompt}
                    ],
                    "temperature": 0.2,
                    "stream": False,
                    "format": "json",
                    "options": {
                        "num_predict": 1200  # Max tokens to prevent truncation
                    }
                }
                retry_resp = requests.post(
                    self._chat_endpoint(),
                    json=retry_payload,
                    timeout=self.timeout
                )
                retry_resp.raise_for_status()
                retry_data = retry_resp.json()
                retry_choices = retry_data.get("choices", [])
                if retry_choices:
                    content = retry_choices[0].get("message", {}).get("content", "")
                    logger.info("Retry completed")

            # Parse JSON from response (extract from envelope if present)
            json_data = self._parse_json(content)
            logger.info(f"Ollama extraction successful")
            return json_data

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Ollama request failed: {e}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Ollama response is not valid JSON: {e}")

    def _parse_json(self, text: str) -> dict:
        """Extract and parse JSON from Ollama response with strict validation.
        
        Extracts from envelope format if present: {"status": "ok", "profile": {...}}
        
        Raises RuntimeError if JSON is invalid (aborts extraction, prevents caching).
        """
        from json_validator import JSONValidator
        
        try:
            # Try extracting from envelope first
            profile_data = JSONValidator.extract_from_envelope(text)
            if profile_data:
                logger.debug("Extracted profile from JSON envelope")
                return profile_data
            
            # Fallback to direct parsing
            parsed = JSONValidator.validate_and_parse(text, abort_on_failure=True)
            if parsed:
                return parsed
            else:
                raise RuntimeError("JSON validation returned None")
        except ValueError as e:
            # Invalid JSON - abort extraction, don't cache
            raise RuntimeError(f"Invalid JSON from Ollama: {e}") from e
