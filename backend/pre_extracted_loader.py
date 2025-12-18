"""Pre-extracted JSON loader for demo/evaluation mode.

If LLM extraction is unstable, load pre-extracted structured JSON
from cache/pre_extracted/ directory. Behaves as if extracted by offline LLM.
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from schema import CompanyProfile
from post_extraction_validator import validate_profile, ExtractionValidationError

logger = logging.getLogger(__name__)


class PreExtractedLoader:
    """Loads pre-extracted company profiles for demo mode."""
    
    def __init__(self, pre_extracted_dir: str = "cache/pre_extracted"):
        self.pre_extracted_dir = Path(pre_extracted_dir)
        self.pre_extracted_dir.mkdir(parents=True, exist_ok=True)
    
    def get_pre_extracted_path(self, domain: str) -> Path:
        """Get path to pre-extracted JSON for domain."""
        return self.pre_extracted_dir / f"{domain}.json"
    
    def has_pre_extracted(self, domain: str) -> bool:
        """Check if pre-extracted data exists for domain."""
        return self.get_pre_extracted_path(domain).exists()
    
    def load_pre_extracted(self, domain: str) -> Optional[CompanyProfile]:
        """Load pre-extracted profile if available and valid.
        
        Args:
            domain: Company domain
            
        Returns:
            CompanyProfile if valid pre-extracted data exists, None otherwise
        """
        pre_extracted_path = self.get_pre_extracted_path(domain)
        
        if not pre_extracted_path.exists():
            return None
        
        try:
            with open(pre_extracted_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Validate structure
            if 'profile' not in data:
                logger.warning(f"Pre-extracted data missing 'profile' field for {domain}")
                return None
            
            # Create and validate profile
            profile = CompanyProfile(**data['profile'])
            validate_profile(profile)
            
            logger.info(f"Loaded pre-extracted profile for {domain}")
            return profile
            
        except ExtractionValidationError as e:
            logger.warning(f"Pre-extracted profile validation failed for {domain}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading pre-extracted profile for {domain}: {e}")
            return None
    
    def save_pre_extracted(self, domain: str, profile: CompanyProfile) -> None:
        """Save profile as pre-extracted JSON.
        
        Args:
            domain: Company domain
            profile: Validated company profile
        """
        try:
            validate_profile(profile)
            
            data = {
                "domain": domain,
                "profile": profile.dict(),
                "source": "pre_extracted",
                "offline": True
            }
            
            pre_extracted_path = self.get_pre_extracted_path(domain)
            with open(pre_extracted_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"Saved pre-extracted profile for {domain}")
            
        except Exception as e:
            logger.error(f"Error saving pre-extracted profile for {domain}: {e}")

