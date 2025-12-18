"""Persistent cache manager for extracted company profiles.

Implements hard caching requirement:
- Cache location: backend/data/extracted_profiles/<domain>.json
- Cache includes: profile, graph, metadata
- Runtime behavior: Load cache if exists and valid, skip LLM calls
- Cache validation: Schema validation before loading
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from schema import ProcessResponse, CompanyProfile, KnowledgeGraph
from post_extraction_validator import validate_profile, ExtractionValidationError

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages persistent caching of extracted company profiles."""
    
    def __init__(self, cache_dir: str = "data/extracted_profiles"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def get_cache_path(self, domain: str) -> Path:
        """Get cache file path for a domain."""
        return self.cache_dir / f"{domain}.json"
    
    def cache_exists(self, domain: str) -> bool:
        """Check if cache exists for domain."""
        return self.get_cache_path(domain).exists()
    
    def load_cache(self, domain: str) -> Optional[Dict[str, Any]]:
        """Load cached profile if exists and valid.
        
        Args:
            domain: Company domain
            
        Returns:
            Cached data dict if valid, None otherwise
        """
        cache_path = self.get_cache_path(domain)
        
        if not cache_path.exists():
            logger.debug(f"No cache found for {domain}")
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Validate cache structure
            if not isinstance(cache_data, dict):
                logger.warning(f"Invalid cache format for {domain}")
                return None
            
            # Check required fields
            if 'profile' not in cache_data or 'graph' not in cache_data:
                logger.warning(f"Cache missing required fields for {domain}")
                return None
            
            # Validate profile schema
            try:
                profile = CompanyProfile(**cache_data['profile'])
                validate_profile(profile)
                logger.info(f"Cache loaded and validated for {domain}")
                return cache_data
            except ExtractionValidationError as e:
                logger.warning(f"Cache validation failed for {domain}: {e}")
                return None
            except Exception as e:
                logger.warning(f"Cache schema error for {domain}: {e}")
                return None
                
        except json.JSONDecodeError as e:
            logger.warning(f"Cache JSON decode error for {domain}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading cache for {domain}: {e}")
            return None
    
    def save_cache(
        self,
        domain: str,
        profile: CompanyProfile,
        graph: KnowledgeGraph,
        llm_engine_used: str,
        model_name: str = None,
        extraction_confidence: str = "high",
        extraction_status: str = "complete"
    ) -> None:
        """Save extracted profile to cache.
        
        Cache ONLY AFTER schema validation.
        Cache repaired JSON if parsing succeeded.
        
        Args:
            domain: Company domain
            profile: Extracted company profile
            graph: Knowledge graph
            llm_engine_used: LLM provider used (ollama | phi2)
            model_name: Model name (e.g., llama3.1, phi-2)
            extraction_confidence: Confidence level (high | medium | low)
            extraction_status: Status (complete | repaired | partial)
        """
        cache_path = self.get_cache_path(domain)
        
        try:
            # Validate profile before caching
            validate_profile(profile)
            
            # Build cache data
            cache_data = {
                "domain": domain,
                "profile": profile.dict(),
                "graph": graph.dict(),
                "metadata": {
                    "extraction_mode": llm_engine_used.lower(),
                    "model_name": model_name or ("llama3.1" if llm_engine_used.lower() == "ollama" else "phi-2"),
                    "timestamp": datetime.utcnow().isoformat(),
                    "offline": True,
                    "schema_version": "2.0.0",
                    "extraction_confidence": extraction_confidence,
                    "extraction_status": extraction_status
                }
            }
            
            # Save to file
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"Cache saved for {domain} to {cache_path} (status: {extraction_status})")
            
        except ExtractionValidationError as e:
            logger.error(f"Cannot cache invalid profile for {domain}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error saving cache for {domain}: {e}")
            raise
    
    def invalidate_cache(self, domain: str) -> None:
        """Invalidate cache for a domain."""
        cache_path = self.get_cache_path(domain)
        if cache_path.exists():
            cache_path.unlink()
            logger.info(f"Cache invalidated for {domain}")

