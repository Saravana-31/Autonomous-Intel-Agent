"""Phi-2 local LLM provider (offline fallback)."""

import logging
from typing import Dict, Any

from llm_engine import LLMEngine
from .base import BaseLLM

logger = logging.getLogger(__name__)


class Phi2LLM(BaseLLM):
    """Local Phi-2 provider for offline extraction.
    
    Wraps the existing LLMEngine (microsoft/phi-2) for consistent fallback behavior.
    Behavior is identical to the original implementation.
    
    CRITICAL: is_available() does NOT load the model - only checks if it CAN be loaded.
    Model is loaded lazily only when extract() is called AND Ollama is unavailable.
    """

    def __init__(self):
        self._engine = LLMEngine()
        self._loaded = False
        self._availability_checked = False
        self._can_load = None  # Cache whether model can be loaded

    def is_available(self) -> bool:
        """Check if Phi-2 CAN be loaded WITHOUT actually loading it.
        
        This is a lightweight check that does NOT load the model.
        Model loading happens only in extract() when actually needed.
        """
        # If already loaded, it's available
        if self._loaded:
            return True
        
        # If we've already checked availability, return cached result
        if self._availability_checked:
            return self._can_load is True
        
        # Lightweight check: verify transformers can import the model
        # This does NOT load the model into memory
        try:
            from transformers import AutoTokenizer, AutoModelForCausalLM
            # Just check if we can access the model config (doesn't load weights)
            tokenizer = AutoTokenizer.from_pretrained(
                "microsoft/phi-2",
                trust_remote_code=True,
                _fast_init=True
            )
            self._can_load = True
            self._availability_checked = True
            logger.debug("Phi-2 availability check: model can be loaded")
            return True
        except Exception as e:
            logger.debug(f"Phi-2 availability check failed: {e}")
            self._can_load = False
            self._availability_checked = True
            return False

    def get_name(self) -> str:
        return "Phi-2"

    def extract(self, prompt: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data using local Phi-2.
        
        Args:
            prompt: Extraction prompt
            schema: Expected schema (for reference)
            
        Returns:
            Parsed JSON response from Phi-2
            
        Raises:
            RuntimeError: If Phi-2 is not available or extraction fails
        """
        # Check availability WITHOUT loading
        if not self.is_available():
            raise RuntimeError("Phi-2 is not available")
        
        # NOW load the model if not already loaded (lazy loading)
        if not self._loaded:
            logger.info("Loading Phi-2 model (fallback only - Ollama unavailable)")
            try:
                self._engine.load_model()
                self._loaded = True
            except Exception as e:
                logger.error(f"Failed to load Phi-2 model: {e}")
                raise RuntimeError(f"Phi-2 model loading failed: {e}")

        try:
            logger.debug("Sending extraction request to Phi-2 (local)")
            # Add JSON-only prompt header with envelope
            from json_validator import JSONValidator
            json_prompt = JSONValidator.build_json_prompt(prompt, use_envelope=True)
            
            # Use higher max_tokens to prevent truncation
            response = self._engine.generate(json_prompt, max_new_tokens=1200, temperature=0.0)
            
            # Check completeness
            is_complete, issue = JSONValidator.check_completeness(response)
            if not is_complete:
                logger.warning(f"Phi-2 output incomplete: {issue}")
                # Retry once
                retry_prompt = f"""The previous JSON was truncated: {response[:200]}...
Return the FULL corrected JSON only. Complete all fields."""
                retry_prompt_full = JSONValidator.build_json_prompt(retry_prompt, use_envelope=True)
                response = self._engine.generate(retry_prompt_full, max_new_tokens=1200, temperature=0.0)
            
            # Parse JSON (extract from envelope if present)
            profile_data = JSONValidator.extract_from_envelope(response)
            if profile_data:
                logger.info("Phi-2 extraction successful (from envelope)")
                return profile_data
            
            parsed = JSONValidator.validate_and_parse(response, abort_on_failure=True)
            if parsed:
                logger.info("Phi-2 extraction successful")
                return parsed
            else:
                raise RuntimeError("Phi-2 JSON validation returned None")

        except Exception as e:
            raise RuntimeError(f"Phi-2 extraction failed: {e}")
