"""Defensive JSON parser with strict validation and 3-stage repair.

Implements mandatory JSON validation & repair:
- Stage 1: Strict parse
- Stage 2: Boundary recovery (first { to last })
- Stage 3: Quote normalization
- Output completeness checks
- Abort if Stage 3 fails (DO NOT cache)
"""

import json
import re
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class JSONValidator:
    """Strict JSON validator and repairer with 3-stage repair."""
    
    SYSTEM_PROMPT_HEADER = """You are a data extraction engine.
Output ONLY valid JSON.
No explanations. No markdown.
If data is missing, return "not_found".
Do not truncate. Do not stop early. Do not use single quotes."""
    
    @staticmethod
    def check_completeness(text: str) -> Tuple[bool, str]:
        """Check if JSON output appears complete.
        
        Args:
            text: Raw JSON text
            
        Returns:
            (is_complete, issue_description)
        """
        text = text.strip()
        
        # Check 1: Ends with }
        if not text.endswith('}'):
            return False, "Output does not end with }"
        
        # Check 2: Quote count is even
        double_quotes = text.count('"')
        single_quotes = text.count("'")
        if double_quotes % 2 != 0 and single_quotes % 2 != 0:
            return False, "Unmatched quotes detected"
        
        # Check 3: No unterminated strings (basic check)
        # Look for unclosed string patterns
        if re.search(r':\s*"[^"]*$', text) or re.search(r':\s*\'[^\']*$', text):
            return False, "Unterminated string detected"
        
        # Check 4: Has opening and closing braces
        open_braces = text.count('{')
        close_braces = text.count('}')
        if open_braces == 0 or close_braces == 0:
            return False, "Missing braces"
        if open_braces > close_braces:
            return False, "Unclosed braces"
        
        return True, ""
    
    @staticmethod
    def validate_and_parse(text: str, abort_on_failure: bool = True) -> Optional[Dict[str, Any]]:
        """Validate and parse JSON with 3-stage defensive repair.
        
        Stage 1: Strict parse
        Stage 2: Boundary recovery (extract first { to last })
        Stage 3: Quote normalization
        
        Args:
            text: Raw text that should contain JSON
            abort_on_failure: If True, raise exception on failure (don't cache)
            
        Returns:
            Parsed JSON dict or None if abort_on_failure=False
            
        Raises:
            ValueError: If JSON is invalid and abort_on_failure=True
        """
        if not text or not isinstance(text, str):
            if abort_on_failure:
                raise ValueError("Empty or invalid input text")
            return None
        
        text = text.strip()
        
        # STAGE 1: Try strict json.loads
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                logger.debug("JSON parsed successfully (Stage 1: strict)")
                return data
        except json.JSONDecodeError:
            pass
        
        # STAGE 2: Boundary recovery - extract from first { to last }
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            extracted = match.group()
            try:
                data = json.loads(extracted)
                if isinstance(data, dict):
                    logger.debug("JSON parsed successfully (Stage 2: boundary recovery)")
                    return data
            except json.JSONDecodeError:
                # Continue to Stage 3
                text = extracted
        
        # STAGE 3: Quote normalization
        cleaned = text
        # Remove markdown code blocks
        cleaned = re.sub(r'```json\s*', '', cleaned)
        cleaned = re.sub(r'```\s*', '', cleaned)
        # Remove trailing commas
        cleaned = re.sub(r',(\s*[}\]])', r'\1', cleaned)
        
        # Replace single quotes with double quotes ONLY for JSON-safe keys
        # Only replace if it looks like Python dict syntax
        if "'" in cleaned and '"' not in cleaned:
            # Try replacing single quotes with double quotes
            cleaned = cleaned.replace("'", '"')
            try:
                data = json.loads(cleaned)
                if isinstance(data, dict):
                    logger.debug("JSON parsed successfully (Stage 3: quote normalization)")
                    return data
            except json.JSONDecodeError:
                pass
        
        # Try extracting again after cleaning
        match = re.search(r'\{[\s\S]*\}', cleaned)
        if match:
            try:
                data = json.loads(match.group())
                if isinstance(data, dict):
                    logger.debug("JSON parsed successfully (Stage 3: cleaned extraction)")
                    return data
            except json.JSONDecodeError:
                pass
        
        # All stages failed - abort
        error_msg = f"Invalid JSON - all repair stages failed: {text[:200]}"
        logger.error(error_msg)
        
        if abort_on_failure:
            raise ValueError(error_msg)
        
        return None
    
    @staticmethod
    def extract_from_envelope(text: str) -> Optional[Dict[str, Any]]:
        """Extract profile data from JSON envelope.
        
        Expected format:
        {
          "status": "ok",
          "profile": { ... }
        }
        
        Args:
            text: Raw JSON text
            
        Returns:
            Extracted profile dict or None
        """
        try:
            data = JSONValidator.validate_and_parse(text, abort_on_failure=False)
            if not data:
                return None
            
            # Check for envelope format
            if "profile" in data:
                return data["profile"]
            if "status" in data and data.get("status") == "ok":
                # Profile might be nested
                return data.get("profile")
            
            # No envelope, return as-is
            return data
        except Exception:
            return None
    
    @staticmethod
    def build_json_prompt(user_prompt: str, use_envelope: bool = True) -> str:
        """Build prompt with JSON-only system header and envelope wrapper.
        
        Args:
            user_prompt: User extraction prompt
            use_envelope: If True, wrap in JSON envelope format
            
        Returns:
            Full prompt with system header
        """
        envelope_instruction = ""
        if use_envelope:
            envelope_instruction = """
CRITICAL: Wrap your response in this exact format:
{
  "status": "ok",
  "profile": {
    ...your extracted data here...
  }
}

The parser will extract from the "profile" field."""
        
        return f"""{JSONValidator.SYSTEM_PROMPT_HEADER}
{envelope_instruction}

{user_prompt}

Remember: Output ONLY valid JSON. No markdown. No explanations. Do not truncate."""

