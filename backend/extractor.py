"""Company intelligence extraction using the LLM."""

import json
import re
from typing import Optional
from schema import CompanyProfile, KeyPerson, ContactInfo
from llm_engine import get_engine


class CompanyExtractor:
    """Extracts structured company information from text using LLM."""
    
    EXTRACTION_PROMPT = '''Extract company information from the following text. Return ONLY valid JSON matching this exact schema:
{{
  "company_name": "string or empty",
  "description_short": "one sentence description or empty",
  "industry": "string or empty",
  "products_services": ["list of products/services"],
  "locations": ["list of locations"],
  "key_people": [{{"name": "string", "title": "string", "role_category": "executive/founder/manager/other"}}],
  "contact": {{"email": "string or null", "phone": "string or null"}},
  "tech_stack": ["list of technologies"]
}}

Rules:
- Only extract information explicitly stated in the text
- Use empty string "" for missing text fields
- Use empty array [] for missing list fields
- Use null for missing optional fields
- Do NOT make up or guess any information

Text to analyze:
{text}

JSON output:'''

    def __init__(self):
        self.engine = get_engine()
    
    def extract(self, text: str) -> CompanyProfile:
        """
        Extract company profile from text.
        
        Args:
            text: Cleaned website text
            
        Returns:
            CompanyProfile with extracted information
        """
        prompt = self.EXTRACTION_PROMPT.format(text=text)
        
        response = self.engine.generate(prompt, max_new_tokens=600)
        
        # Parse the JSON from response
        profile_dict = self._parse_json_response(response)
        
        # Convert to Pydantic model with validation
        return self._dict_to_profile(profile_dict)
    
    def _parse_json_response(self, response: str) -> dict:
        """Parse JSON from LLM response."""
        # Try to find JSON in the response
        response = response.strip()
        
        # Look for JSON object
        json_match = re.search(r'\{[\s\S]*\}', response)
        
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # Try cleaning common issues
        cleaned = response
        cleaned = re.sub(r',\s*}', '}', cleaned)  # Remove trailing commas
        cleaned = re.sub(r',\s*]', ']', cleaned)
        
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Return empty dict if parsing fails
            return {}
    
    def _dict_to_profile(self, data: dict) -> CompanyProfile:
        """Convert dictionary to CompanyProfile with safe defaults."""
        # Process key_people
        key_people = []
        for person in data.get("key_people", []):
            if isinstance(person, dict):
                key_people.append(KeyPerson(
                    name=person.get("name", ""),
                    title=person.get("title", ""),
                    role_category=person.get("role_category", "")
                ))
        
        # Process contact
        contact_data = data.get("contact", {})
        if isinstance(contact_data, dict):
            contact = ContactInfo(
                email=contact_data.get("email"),
                phone=contact_data.get("phone")
            )
        else:
            contact = ContactInfo()
        
        # Build profile
        return CompanyProfile(
            company_name=data.get("company_name", ""),
            description_short=data.get("description_short", ""),
            industry=data.get("industry", ""),
            products_services=self._ensure_list(data.get("products_services", [])),
            locations=self._ensure_list(data.get("locations", [])),
            key_people=key_people,
            contact=contact,
            tech_stack=self._ensure_list(data.get("tech_stack", []))
        )
    
    def _ensure_list(self, value) -> list:
        """Ensure value is a list of strings."""
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if item]
