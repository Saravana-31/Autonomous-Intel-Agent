"""Base LLM interface for the tiered extraction system."""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any

logger = logging.getLogger(__name__)


class BaseLLM(ABC):
    """Abstract base class for LLM providers.
    
    All providers must implement extract() and validate responses
    against the mandatory field schema.
    """

    @abstractmethod
    def extract(self, prompt: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured data using the LLM.
        
        Args:
            prompt: The extraction prompt
            schema: Expected output schema (for validation)
            
        Returns:
            Extracted data as dictionary matching schema
            
        Raises:
            Exception: If extraction fails or response invalid
        """
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this LLM is available and healthy."""
        raise NotImplementedError

    @abstractmethod
    def get_name(self) -> str:
        """Return the name of this LLM provider."""
        raise NotImplementedError
