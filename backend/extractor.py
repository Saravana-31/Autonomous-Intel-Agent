"""Company intelligence extraction using the LLM."""

import json
import re
import time
import logging
from typing import Optional, Tuple
from schema import CompanyProfile, KeyPerson, ContactInfo
from llm_engine import get_engine

logger = logging.getLogger(__name__)


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

        start = time.time()
        response = self.engine.generate(prompt, max_new_tokens=600)
        duration = time.time() - start
        logger.info(f"LLM extraction completed in {duration:.2f}s")
        
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

    def _extract_value_and_confidence(self, raw) -> Tuple[Optional[str], Optional[float]]:
        """Handle values that may be plain or objects with confidence.

        Accepts forms like:
         - "Acme Corp"
         - {"value": "Acme Corp", "confidence": 0.92}
         - {"text": "Acme Corp", "score": 0.8}
        Returns (value, confidence)
        """
        if raw is None:
            return None, None
        if isinstance(raw, dict):
            # common keys
            val = raw.get("value") or raw.get("text") or raw.get("name")
            conf = raw.get("confidence") or raw.get("score")
            try:
                if conf is not None:
                    conf = float(conf)
            except Exception:
                conf = None
            return (str(val) if val is not None else None), conf
        # primitive
        return (str(raw), None)
    
    def _dict_to_profile(self, data: dict) -> CompanyProfile:
        """Convert dictionary to CompanyProfile with safe defaults."""
        confidences = {}
        # Process key_people
        key_people = []
        for person in data.get("key_people", []):
            if isinstance(person, dict):
                name, name_conf = self._extract_value_and_confidence(person.get("name"))
                title, title_conf = self._extract_value_and_confidence(person.get("title"))
                role = person.get("role_category", "")
                if name_conf is not None:
                    confidences[f"key_people.{name}.name"] = name_conf
                if title_conf is not None:
                    confidences[f"key_people.{name}.title"] = title_conf
                key_people.append(KeyPerson(
                    name=name or "",
                    title=title or "",
                    role_category=role or ""
                ))
        
        # Process contact
        contact_data = data.get("contact", {})
        if isinstance(contact_data, dict):
            email, email_conf = self._extract_value_and_confidence(contact_data.get("email"))
            phone, phone_conf = self._extract_value_and_confidence(contact_data.get("phone"))
            if email_conf is not None:
                confidences["contact.email"] = email_conf
            if phone_conf is not None:
                confidences["contact.phone"] = phone_conf
            contact = ContactInfo(
                email=email,
                phone=phone
            )
        else:
            contact = ContactInfo()
        
        # Build profile
        # Handle possible confidence-wrapped fields for strings and lists
        company_name, company_conf = self._extract_value_and_confidence(data.get("company_name", ""))
        if company_conf is not None:
            confidences["company_name"] = company_conf

        description_short, desc_conf = self._extract_value_and_confidence(data.get("description_short", ""))
        if desc_conf is not None:
            confidences["description_short"] = desc_conf

        industry, industry_conf = self._extract_value_and_confidence(data.get("industry", ""))
        if industry_conf is not None:
            confidences["industry"] = industry_conf

        # Lists where items may include confidence
        def extract_list_items(raw_list, field_name):
            items = []
            for i, itm in enumerate(raw_list or []):
                val, conf = self._extract_value_and_confidence(itm)
                if conf is not None:
                    confidences[f"{field_name}.{i}"] = conf
                if val:
                    items.append(val)
            return items

        products_services = extract_list_items(data.get("products_services", []), "products_services")
        locations = extract_list_items(data.get("locations", []), "locations")
        tech_stack = extract_list_items(data.get("tech_stack", []), "tech_stack")

        # Log collected confidences (bonus feature) without changing schema
        if confidences:
            logger.info(f"Extracted field confidences: {confidences}")

        return CompanyProfile(
            company_name=company_name or data.get("company_name", ""),
            description_short=description_short or data.get("description_short", ""),
            industry=industry or data.get("industry", ""),
            products_services=products_services,
            locations=locations,
            key_people=key_people,
            contact=contact,
            tech_stack=tech_stack
        )
    
    def _ensure_list(self, value) -> list:
        """Ensure value is a list of strings."""
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if item]
