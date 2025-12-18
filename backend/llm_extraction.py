"""LLM-powered extraction for semantic tasks.

Uses Ollama for:
- Long description generation (4-6 sentence summary)
- Industry / sub-industry classification
- Role normalization (to allowed categories)
- Person name validation
"""

import json
import logging
from typing import Dict, Any, List, Optional

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

logger = logging.getLogger(__name__)


class LLMExtraction:
    """LLM-based extraction for semantic tasks."""

    # Allowed role categories per requirements
    ALLOWED_ROLES = {"Founder", "Executive", "Director", "Manager", "Employee"}

    @staticmethod
    def normalize_roles(people_raw: List[str], llm_response: Optional[str] = None) -> List[Dict[str, str]]:
        """Normalize roles for an already-validated list of people.

        IMPORTANT: This function must NOT invent person names. `people_raw` is expected
        to be a list of validated names (from deterministic layer). Return list of dicts
        with `name`, `title` (may be 'not_found'), and `role_category` mapped to allowed classes.
        """
        people_normalized = []

        title_to_role = {
            'founder': 'Founder',
            'co-founder': 'Founder',
            'ceo': 'Executive',
            'chief executive': 'Executive',
            'cto': 'Executive',
            'cfo': 'Executive',
            'president': 'Executive',
            'vice president': 'Executive',
            'director': 'Director',
            'manager': 'Manager',
            'lead': 'Manager',
            'head': 'Manager'
        }

        for person in people_raw:
            # Expect person to be either a string name or dict with name/title
            if isinstance(person, dict):
                name = person.get('name')
                title = person.get('title', 'not_found')
            else:
                name = person
                title = 'not_found'

            if not name:
                continue

            # map title to role_category using heuristics
            role = 'Employee'
            tlower = title.lower() if isinstance(title, str) else ''
            for k, v in title_to_role.items():
                if k in tlower:
                    role = v
                    break

            # If LLM response provided with explicit mapping, attempt to use it only for role categories
            # but do not accept new person names from LLM
            if llm_response and isinstance(llm_response, str):
                # simple check for role mention near the name
                if name and name in llm_response and any(k in llm_response.lower() for k in title_to_role.keys()):
                    for k, v in title_to_role.items():
                        if k in llm_response.lower():
                            role = v
                            break

            people_normalized.append({
                'name': name,
                'title': title if title else 'not_found',
                'role_category': role
            })

        return people_normalized

    @staticmethod
    def build_llm_prompt(
        text: str,
        company_name: str,
        products_services: List[str],
        domain: str,
        html_files: List = None
    ) -> str:
        """Build LLM prompt for semantic extraction.
        
        Args:
            text: Company text content (combined from all pages)
            company_name: Extracted company name
            products_services: Raw products/services list
            domain: Company domain
            html_files: Optional list of (filename, content) tuples for context
            
        Returns:
            Structured LLM prompt
        """
        
        # Build content summary from multiple pages if available
        content_sections = []
        if html_files and BeautifulSoup:
            for filename, content in html_files:
                page_type = "homepage" if "index" in filename.lower() else \
                           "about" if "about" in filename.lower() else \
                           "services" if any(kw in filename.lower() for kw in ["service", "product", "offer"]) else \
                           "other"
                # Extract text snippet (first 500 chars)
                try:
                    soup = BeautifulSoup(content, 'html.parser')
                    page_text = soup.get_text(separator=' ', strip=True)[:500]
                    if page_text:
                        content_sections.append(f"{page_type.upper()} PAGE ({filename}): {page_text}...")
                except:
                    pass
        
        # Combine all content - use sections if available, otherwise use provided text
        combined_content = "\n\n".join(content_sections) if content_sections else text[:2000]
        
        prompt = f"""You are an expert business analyst. Extract structured information ONLY from the provided company website content.

CRITICAL RULES:
- Extract ONLY information explicitly stated in the content
- If information is not present, use "not_found" (NEVER use "unknown")
- Do NOT invent, assume, or hallucinate any information
- Do NOT create fake people, products, or services
- If you cannot confidently extract a field, set it to "not_found"
- Combine information from homepage, about page, and services/products pages if available

COMPANY: {company_name}
DOMAIN: {domain}
CONTENT FROM MULTIPLE PAGES:
{combined_content}

TASK 1: Generate Short and Long Descriptions
- Short Description: Create a concise 1-2 sentence company description summarizing what the company does.
  Use text from homepage, about page, services/products pages if available.
  If no marketing description exists, summarize what the company does based on services/products mentioned.
  DO NOT repeat company name unnecessarily (e.g., avoid "CompanyName (domain.com)").
  Focus on what the company provides/does.
- Long Description: Maximum 3 sentences. Maximum 80 words. Must end with a period.
  Create a comprehensive company description based ONLY on the content provided.
  Combine: what the company does, mission/vision (if mentioned), target market (if mentioned), key strengths (if mentioned).
  If any of these are not mentioned, omit them - do NOT invent.
  DO NOT repeat company name unnecessarily.
  CRITICAL: Keep under 80 words to prevent truncation.

TASK 2: Classify Industry and Sub-Industry
From the content, determine:
- Primary Industry (e.g., "Software", "Finance", "Healthcare", "Retail", "Manufacturing")
- Sub-Industry (e.g., "SaaS", "FinTech", "Medical Devices", "E-commerce", "Industrial Equipment")
If you cannot determine from content, use "not_found" (NOT "unknown")

TASK 3: Normalize Product/Service Categories
Current raw list: {json.dumps(products_services)}
Categorize each item as either "Product" (tangible item) or "Service" (intangible offering).
Only include items that are clearly products or services - exclude certifications, menu items, headings.

RESPOND WITH VALID JSON ONLY (no markdown, no explanations, no code blocks):
{{
    "short_description": "string (1-2 sentences summarizing what company does, or 'not_found' if insufficient info)",
    "long_description": "string (4-6 sentences based on content, or 'not_found' if insufficient info)",
    "industry": "string (or 'not_found')",
    "sub_industry": "string (or 'not_found')",
    "products": ["list of product names from content only"],
    "services": ["list of service names from content only"]
}}"""
        
        return prompt

    @staticmethod
    def parse_llm_response(llm_json: str) -> Dict[str, Any]:
        """Parse and validate LLM JSON response with strict validation and field completeness.
        
        Uses JSONValidator for defensive parsing.
        Extracts from envelope format if present.
        Enforces field completeness (injects "not_found" for missing fields).
        
        Args:
            llm_json: Raw LLM JSON response
            
        Returns:
            Parsed dict with extracted fields (all required fields guaranteed)
            
        Raises:
            ValueError: If JSON is invalid (prevents caching)
        """
        from json_validator import JSONValidator
        
        # Use defensive JSON validator - try envelope extraction first
        try:
            # Try extracting from envelope
            profile_data = JSONValidator.extract_from_envelope(llm_json)
            if profile_data:
                data = profile_data
                logger.debug("Extracted profile from JSON envelope")
            else:
                # Fallback to direct parsing
                data = JSONValidator.validate_and_parse(llm_json, abort_on_failure=True)
            
            if not data:
                raise ValueError("JSON validation returned None")
            
            # FIELD COMPLETENESS ENFORCEMENT - guarantee all required fields exist
            required_fields = {
                'short_description': 'not_found',
                'long_description': 'not_found',
                'industry': 'not_found',
                'sub_industry': 'not_found'
            }
            
            for field, default_value in required_fields.items():
                if field not in data or not data[field] or data[field].lower() == 'unknown':
                    data[field] = default_value
                    logger.debug(f"Injected '{default_value}' for missing field: {field}")
            
            # Ensure lists exist (never null)
            data['products'] = data.get('products', [])
            data['services'] = data.get('services', [])
            
            # Validate long_description length (enforce 80 word limit)
            if 'long_description' in data and data['long_description'] != 'not_found':
                words = data['long_description'].split()
                if len(words) > 80:
                    # Truncate to 80 words and ensure ends with period
                    truncated = ' '.join(words[:80])
                    if not truncated.endswith('.'):
                        truncated += '.'
                    data['long_description'] = truncated
                    logger.debug("Truncated long_description to 80 words")
            
            return data
            
        except ValueError as e:
            # Re-raise to prevent caching
            logger.error(f"LLM JSON validation failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")
            raise ValueError(f"LLM response parsing failed: {e}") from e

    @staticmethod
    def validate_location(location_text: str, html_count: int = 1) -> bool:
        """Validate location confidence.
        
        Location must:
        - Appear ≥ 2 times in HTML, OR
        - Be in structured address block
        
        Args:
            location_text: Location string
            html_count: Number of times found in HTML
            
        Returns:
            True if location meets confidence threshold
        """
        # If found multiple times, include it
        if html_count >= 2:
            return True
        
        # Check if it looks like a real address
        required_parts = any(kw in location_text.lower() for kw in [
            'address', 'street', 'building', 'floor', 'suite',
            'city', 'state', 'postal', 'zip', 'country'
        ])
        
        return required_parts

    @staticmethod
    def validate_person_name(name: str) -> bool:
        """Validate person name to prevent hallucinations.
        
        Must:
        - Have ≥ 2 words
        - Not be a slogan or marketing phrase
        - Look like a real human name
        
        Args:
            name: Name to validate
            
        Returns:
            True if valid person name
        """
        # Must have at least 2 words
        words = name.split()
        if len(words) < 2:
            return False
        
        # Reject common slogans/marketing phrases
        slogans = [
            'our mission', 'our vision', 'our values',
            'about us', 'contact us', 'join us',
            'welcome', 'hello', 'thank you', 'best',
            'innovative', 'excellence', 'trusted'
        ]
        
        name_lower = name.lower()
        if any(slogan in name_lower for slogan in slogans):
            return False
        
        # Each word should start with capital (name-like pattern)
        for word in words:
            if not word[0].isupper():
                return False
            if not word.replace('-', '').replace("'", '').isalpha():
                return False
        
        return True

