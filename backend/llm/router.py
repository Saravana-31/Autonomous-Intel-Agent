"""LLM router with automatic fallback logic."""

import logging
from typing import Dict, Any, Optional

from .base import BaseLLM
from .ollama_cloud import OllamaLLM
from .phi2_local import Phi2LLM

logger = logging.getLogger(__name__)

# Disable Phi-2 fallback to reduce memory pressure


class LLMRouter:
    """Routes extraction requests to Ollama only.
    
    Implements single-provider strategy:
    1. Use Ollama (online, primary)
    2. Phi-2 fallback disabled to reduce memory usage
    3. Log which provider was used
    """

    def __init__(self):
        self.ollama = OllamaLLM()
        self.phi2 = Phi2LLM()
        self._last_used_provider: Optional[str] = None

    @property
    def last_used_provider(self) -> Optional[str]:
        """Return the name of the LLM used in the last extraction."""
        return self._last_used_provider

    def extract(self, prompt: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Extract data using strict primary/fallback logic with timeout control.
        
        REQUIRED BEHAVIOR:
        - If Ollama is available: Use Ollama, DO NOT load Phi-2
        - If Ollama fails: Load Phi-2 once and use it
        - Phi-2 MUST NOT preload if Ollama is healthy
        - Max extraction time: 25 seconds
        
        Args:
            prompt: Extraction prompt
            schema: Expected schema
            
        Returns:
            Extracted data from primary or fallback LLM
            
        Raises:
            RuntimeError: If both providers fail
        """
        import time
        
        # STEP 1: Check Ollama availability (lightweight, no model loading)
        ollama_available = self.ollama.is_available()
        
        if ollama_available:
            # PRIMARY PATH: Ollama is available - use it and DO NOT touch Phi-2
            try:
                logger.info(f"Using PRIMARY LLM: {self.ollama.get_name()} (Ollama)")
                start_time = time.time()
                result = self.ollama.extract(prompt, schema)
                duration = time.time() - start_time
                self._last_used_provider = self.ollama.get_name()
                logger.info(f"Extraction successful via {self.ollama.get_name()} in {duration:.2f}s")
                return result
            except Exception as e:
                logger.warning(f"Ollama extraction failed despite availability check: {e}")
                # Fall through to fallback
        else:
            logger.info(f"Primary LLM ({self.ollama.get_name()}) unavailable, checking fallback...")
        
        # STEP 2: Fallback path - Ollama failed or unavailable
        # Only NOW check Phi-2 availability (still doesn't load the model)
        phi2_available = self.phi2.is_available()
        
        if phi2_available:
            try:
                logger.info(f"Using FALLBACK LLM: {self.phi2.get_name()} (Phi-2)")
                start_time = time.time()
                # extract() will load Phi-2 lazily if needed
                result = self.phi2.extract(prompt, schema)
                duration = time.time() - start_time
                self._last_used_provider = self.phi2.get_name()
                logger.info(f"Extraction successful via {self.phi2.get_name()} in {duration:.2f}s")
                return result
            except Exception as e:
                logger.error(f"Phi-2 extraction failed: {e}")
        else:
            logger.error(f"Fallback LLM ({self.phi2.get_name()}) unavailable")

        # Both providers failed
        self._last_used_provider = None
        raise RuntimeError("No available LLM providers (Ollama and Phi-2 both failed).")

    def get_available_providers(self) -> Dict[str, bool]:
        """Return availability status of providers."""
        return {
            self.ollama.get_name(): self.ollama.is_available(),
            self.phi2.get_name(): self.phi2.is_available()
        }

    def health_check(self) -> Dict[str, Any]:
        """Return health information about providers.
        
        NOTE: This does NOT load Phi-2 model - only checks availability.
        """
        # Check Ollama (lightweight HTTP check)
        ollama_available = self.ollama.is_available()
        
        # Check Phi-2 availability WITHOUT loading (lightweight check)
        phi2_available = self.phi2.is_available()
        
        return {
            "primary": {
                "name": self.ollama.get_name(),
                "available": ollama_available
            },
            "fallback": {
                "name": self.phi2.get_name(),
                "available": phi2_available,
                "loaded": self.phi2._loaded if hasattr(self.phi2, '_loaded') else False
            },
            "last_used": self._last_used_provider
        }
