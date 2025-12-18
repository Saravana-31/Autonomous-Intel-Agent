"""Deterministic extraction layer using regex, HTML parsing, and heuristics.

This layer extracts:
- Emails, phone numbers, social links
- Addresses, city, country
- Domain, company name
- Service/product raw names
- Certifications (keyword-based)
- Logo URLs with priority rules
- Contact page URLs
- Tech stack signals
- Location type classification (HQ vs Office)

No LLM required — fast and reliable.
"""

import re
import logging
from typing import List, Set, Tuple, Dict, Any
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class DeterministicExtractor:
    """Rule-based extraction without LLM."""

    # Regex patterns
    EMAIL_PATTERN = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    PHONE_PATTERN = r'\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b'
    URL_PATTERN = r'https?://(?:www\.)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}'
    
    # Certification keywords
    CERTIFICATION_KEYWORDS = {
        'ISO 9001', 'ISO 14001', 'ISO 45001', 'ISO 27001',
        'SOC 2', 'GDPR', 'HIPAA', 'PCI-DSS',
        'ITIL', 'AWS', 'Azure', 'GCP', 'Linux',
        'certified', 'accredited', 'license', 'certification'
    }
    
    # Country patterns
    COUNTRY_PATTERNS = {
        'United States': r'\b(USA|US|U\.S\.|United States|America|US$)',
        'India': r'\b(India|IN$)',
        'United Kingdom': r'\b(UK|U\.K\.|United Kingdom|England|Scotland|Wales)',
        'Canada': r'\b(Canada|CA|CAN)',
        'Australia': r'\b(Australia|AU|AUS)',
        'Germany': r'\b(Germany|DE|DEU)',
        'France': r'\b(France|FR|FRA)',
    }

    @staticmethod
    def extract_emails(text: str) -> List[str]:
        """Extract email addresses from text."""
        emails = re.findall(DeterministicExtractor.EMAIL_PATTERN, text)
        return list(set(emails))  # Deduplicate

    @staticmethod
    def extract_phone_numbers(text: str) -> List[str]:
        """Extract phone numbers from text."""
        matches = re.finditer(DeterministicExtractor.PHONE_PATTERN, text)
        phones = []
        for match in matches:
            # Reconstruct phone number
            phone = f"({match.group(1)}) {match.group(2)}-{match.group(3)}"
            phones.append(phone)
        return list(set(phones))

    @staticmethod
    def extract_social_links(text: str) -> List[Tuple[str, str]]:
        """Extract social media links as (platform, url) tuples."""
        social_patterns = {
            'linkedin': r'(https?://(?:www\.)?linkedin\.com/[\w\-]+)',
            'twitter': r'(https?://(?:www\.)?twitter\.com/[\w\-]+)',
            'facebook': r'(https?://(?:www\.)?facebook\.com/[\w\-]+)',
            'github': r'(https?://(?:www\.)?github\.com/[\w\-]+)',
            'instagram': r'(https?://(?:www\.)?instagram\.com/[\w\-]+)',
        }
        
        links = []
        for platform, pattern in social_patterns.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                url = match.group(1)
                links.append((platform.capitalize(), url))
        
        return links

    @staticmethod
    def extract_domain(text: str, default: str = "not_found") -> str:
        """Extract domain from text (from URL patterns or metadata)."""
        # Try to find www. or domain-like patterns
        domain_match = re.search(r'(?:www\.)?([a-zA-Z0-9-]+\.(?:com|org|net|io|co|uk|de|fr|in))', text)
        if domain_match:
            return domain_match.group(1)
        
        # Try to extract from URLs
        urls = re.findall(DeterministicExtractor.URL_PATTERN, text)
        if urls:
            return urls[0]
        
        return default

    @staticmethod
    def extract_company_name(text: str, domain: str = "", default: str = "not_found") -> str:
        """Extract company name from text or domain."""
        # Try to extract from title/heading
        title_match = re.search(r'<title>([^<]+)</title>', text, re.IGNORECASE)
        if title_match:
            title = title_match.group(1).strip()
            # Clean up common suffixes
            title = re.sub(r'\s*[-|].*', '', title)
            if len(title) > 2:
                return title
        
        # Try to clean domain
        if domain and domain != "not_found":
            company_name = domain.split('.')[0].title()
            if len(company_name) > 2:
                return company_name
        
        return default

    @staticmethod
    def extract_address_parts(text: str) -> Tuple[str, str, str]:
        """Extract physical address, city, and country with sanitization.
        
        Location is valid ONLY IF:
        - Appears near address indicators (Street, Ave, HQ, Office)
        - OR matches postal format
        - OR appears with "based in / located at"
        
        Returns: (address, city, country)
        """
        address = "not_found"
        city = "not_found"
        country = "not_found"

        # Clean html fragments and entities
        text_clean = DeterministicExtractor._clean_fragment(text)

        # Look for common address patterns with context validation
        address_indicators = ['street', 'avenue', 'ave', 'road', 'rd', 'boulevard', 'blvd', 
                             'drive', 'dr', 'lane', 'ln', 'way', 'court', 'ct', 'plaza', 
                             'suite', 'ste', 'floor', 'fl', 'building', 'bldg', 'hq', 
                             'headquarters', 'office', 'located at', 'based in']
        
        # Pattern: Address indicators followed by address-like text
        address_pattern = r'(?:Address|Headquarters|HQ|Located at|Based in|Office)[\s:]*([^,\n]{10,120})'
        address_match = re.search(address_pattern, text_clean, re.IGNORECASE)
        if address_match:
            candidate = address_match.group(1).strip()
            # Validate: must contain address indicator or postal code pattern
            candidate_lower = candidate.lower()
            has_indicator = any(ind in candidate_lower for ind in address_indicators)
            has_postal = bool(re.search(r'\b\d{5}(-\d{4})?\b', candidate))  # US ZIP or similar
            
            if has_indicator or has_postal:
                address = candidate

        # Extract city - must be near address context
        if address != "not_found":
            city_pattern = r'([A-Z][a-zA-Z\-]+)(?:,\s*[A-Z][a-zA-Z\-]+)?(?:,|$)'
            city_match = re.search(city_pattern, address)
            if city_match:
                city_candidate = city_match.group(1)
                # Sanitize: reject common non-city words
                invalid_cities = ['thanks', 'thank', 'you', 'visit', 'contact', 'email', 'phone']
                if city_candidate.lower() not in invalid_cities:
                    city = city_candidate

        # Extract country - validate context
        for country_name, pattern in DeterministicExtractor.COUNTRY_PATTERNS.items():
            # Must appear near address indicators or in structured context
            country_context_pattern = rf'(?:based in|located in|headquarters in|office in|country[:\s]+).*?{pattern}'
            if re.search(country_context_pattern, text_clean, re.IGNORECASE):
                country = country_name
                break
            # Or in address line
            if address != "not_found" and re.search(pattern, address, re.IGNORECASE):
                country = country_name
                break

        return address, city, country

    @staticmethod
    def _clean_fragment(s: str) -> str:
        """Clean HTML fragments, tags, and entities from a small text fragment."""
        if not s:
            return s or ''
        # Remove HTML tags
        s = re.sub(r'<[^>]+>', ' ', s)
        # Remove HTML entities
        s = re.sub(r'&[A-Za-z0-9#]+;', ' ', s)
        # Remove stray closing fragments like 'r</span>' (tags already removed but leftovers may remain)
        s = re.sub(r'[<>/]+', ' ', s)
        # Normalize whitespace
        s = re.sub(r'[\r\n\t]+', ' ', s)
        s = re.sub(r'\s+', ' ', s).strip()
        # Strip leading/trailing punctuation
        return s.strip(' ,;:-')

    @staticmethod
    def extract_services_and_products(text: str) -> Tuple[List[str], List[str]]:
        """Extract raw service and product names from text.
        
        Returns: (services, products)
        """
        services = []
        products = []
        
        # Look for "Services" section
        services_match = re.search(
            r'(?:Services|What We Offer|Our Services)[\s:]*([^.]+?)(?:Products|About|Contact|$)',
            text, re.IGNORECASE | re.DOTALL
        )
        if services_match:
            service_text = services_match.group(1)
            # Split by common delimiters
            items = re.split(r'[•\-*\n,]', service_text)
            for item in items:
                item = item.strip()
                if len(item) > 3 and len(item) < 100:
                    services.append(item)
        
        # Look for "Products" section
        products_match = re.search(
            r'(?:Products|Our Products|Offerings)[\s:]*([^.]+?)(?:Services|About|Contact|$)',
            text, re.IGNORECASE | re.DOTALL
        )
        if products_match:
            product_text = products_match.group(1)
            items = re.split(r'[•\-*\n,]', product_text)
            for item in items:
                item = item.strip()
                if len(item) > 3 and len(item) < 100:
                    products.append(item)
        
        return services, products

    @staticmethod
    def extract_certifications(text: str) -> List[str]:
        """Extract certification names using keyword matching."""
        certifications = []
        for keyword in DeterministicExtractor.CERTIFICATION_KEYWORDS:
            if keyword.lower() in text.lower():
                certifications.append(keyword)
        return list(set(certifications))

    @staticmethod
    def extract_people_mentions(html_text: str, domain: str = "") -> List[str]:
        """Extract person names with stricter heuristics to avoid product/heading pollution.

        Rules (must satisfy at least two):
        - Appear in JSON-LD with @type Person OR
        - Appear in sections/pages likely to contain people (/about, /team, leadership) OR
        - Appear near role keywords (CEO, Founder, Director, Manager, CTO, CFO)

        Returns validated list of names (may be empty). Does NOT invent names.
        """
        from bs4 import BeautifulSoup
        import json
        import re

        soup = BeautifulSoup(html_text, "html.parser")
        candidates = []

        # 1) JSON-LD Person entries (high confidence)
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string or '{}')
            except Exception:
                continue
            # data may be object or graph
            items = []
            if isinstance(data, dict):
                items = [data]
                if '@graph' in data and isinstance(data['@graph'], list):
                    items = data['@graph']
            elif isinstance(data, list):
                items = data

            for item in items:
                try:
                    if isinstance(item, dict) and item.get('@type', '').lower() == 'person':
                        name = item.get('name') or item.get('givenName')
                        if name:
                            candidates.append((name.strip(), 'jsonld'))
                except Exception:
                    continue

        # 2) Look for team/about sections and headings
        role_keywords = ['ceo', 'founder', 'co-founder', 'cto', 'cfo', 'chief', 'director', 'manager', 'lead', 'head']
        section_keywords = ['team', 'about', 'leadership', 'people', 'our team']

        # Find headings that match team/about
        for header in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            text = (header.get_text() or '').lower()
            if any(k in text for k in section_keywords):
                # collect nearby name-like strings (siblings/next elements)
                node = header
                for sibling in node.find_next_siblings(limit=10):
                    stext = sibling.get_text(separator=' ', strip=True)
                    for match in re.finditer(r'\b([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b', stext):
                        candidates.append((match.group(1).strip(), 'section'))

        # 3) Search for role keywords proximity
        body_text = soup.get_text(separator='\n', strip=True)
        for m in re.finditer(r'([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', body_text):
            name = m.group(1)
            # Extract small window around name
            start = max(0, m.start() - 200)
            end = min(len(body_text), m.end() + 200)
            window = body_text[start:end].lower()
            if any(rk in window for rk in role_keywords):
                candidates.append((name.strip(), 'role_nearby'))

        # Deduplicate and validate candidates
        seen = set()
        validated = []
        # blacklist tokens that indicate non-persons
        blacklist = ['service', 'product', 'platform', 'payment', 'pci', 'iso', 'soc', 'certificate', 'certified', 'register', 'policy', 'terms', 'privacy']

        for name, reason in candidates:
            key = name.lower()
            if key in seen:
                continue
            # Basic name validation: at least two words, each word starts with capital letter
            parts = name.split()
            if len(parts) < 2 or len(name) > 60:
                continue
            if any(tok.lower() in key for tok in blacklist):
                continue
            # each token should start uppercase and be alpha or hyphen/apostrophe
            valid_tokens = all(p[0].isupper() and all(ch.isalpha() or ch in "-'" for ch in p) for p in parts)
            if not valid_tokens:
                continue

            # At least two signals must be present: jsonld OR section OR role_nearby
            # If jsonld present, accept immediately; otherwise prefer section+role_nearby
            if reason == 'jsonld':
                validated.append(name)
                seen.add(key)
                continue

            # count supporting signals across the HTML
            support = 0
            if re.search(r'\b(' + '|'.join(role_keywords) + r')\b', body_text.lower()):
                support += 1
            if any(sk in (html_text or '').lower() for sk in section_keywords):
                support += 1

            if support >= 2 or reason == 'section':
                validated.append(name)
                seen.add(key)

            if len(validated) >= 20:
                break

        return validated
    @staticmethod
    def extract_logo_url(html_text: str, domain: str = "", base_url: str = "") -> str:
        """Extract logo URL with priority heuristics.
        
        Priority order:
        1. Images with 'logo' in filename or alt text
        2. Images with 'brand' in filename or alt text
        3. Images in navbar/header
        
        Args:
            html_text: Raw HTML text
            domain: Company domain for context
            base_url: Base URL to convert relative paths to absolute
            
        Returns:
            Logo URL (absolute path) or "unknown"
        """
        try:
            soup = BeautifulSoup(html_text, 'html.parser')
        except Exception as e:
            logger.debug(f"Failed to parse HTML for logo: {e}")
            return "not_found"
        
        logo_url = "not_found"
        max_score = 0
        
        for img in soup.find_all('img'):
            score = 0
            src = img.get('src', '').lower()
            alt = img.get('alt', '').lower()
            title = img.get('title', '').lower()
            
            # Score based on filename/alt/title
            if 'logo' in src or 'logo' in alt or 'logo' in title:
                score += 10
            if 'brand' in src or 'brand' in alt or 'brand' in title:
                score += 7
            if 'icon' in src or 'icon' in alt:
                score += 3
            
            # Prefer larger images (proxy for logo size)
            width = img.get('width', '0')
            if width and width.isdigit() and int(width) > 50:
                score += 2
            
            if score > max_score:
                max_score = score
                img_src = img.get('src', '')
                if img_src:
                    # Convert relative URLs to absolute
                    if img_src.startswith('http'):
                        logo_url = img_src
                    elif img_src.startswith('/'):
                        if base_url:
                            logo_url = urljoin(base_url, img_src)
                        else:
                            logo_url = f"/{img_src.lstrip('/')}"
                    else:
                        if base_url:
                            logo_url = urljoin(base_url, img_src)
                        else:
                            logo_url = f"/{img_src}"
        
        return logo_url if logo_url != "unknown" else "not_found"

    @staticmethod
    def extract_contact_page_url(html_text: str) -> str:
        """Extract contact page URL from navigation links.
        
        Looks for links containing: contact, reach-us, get-in-touch, etc.
        
        Returns:
            Contact page URL or "not_found"
        """
        try:
            soup = BeautifulSoup(html_text, 'html.parser')
        except Exception:
            return "not_found"
        
        contact_keywords = [
            'contact', 'reach-us', 'get-in-touch', 'contact-us',
            'contact-form', 'get-in-touch', 'inquiry', 'support'
        ]
        
        for link in soup.find_all('a', href=True):
            href = link.get('href', '').lower()
            text = link.get_text().lower()
            
            for keyword in contact_keywords:
                if keyword in href or keyword in text:
                    full_href = link.get('href', '')
                    # Return without fragment/query for cleaner URL
                    return full_href.split('?')[0].split('#')[0]
        
        return "not_found"

    @staticmethod
    def extract_tech_stack_signals(html_text: str) -> Dict[str, List[str]]:
        """Detect tech stack signals from HTML patterns.
        
        Detects:
        - CMS: WordPress, Shopify, etc.
        - Analytics: Google Analytics, Mixpanel, etc.
        - Frontend: React, Vue, Angular, etc.
        - Marketing: HubSpot, Marketo, etc.
        
        Returns:
            Dict with tech categories and detected tools
        """
        signals = {
            "cms": [],
            "analytics": [],
            "frontend": [],
            "marketing": []
        }
        
        # CMS detection
        if 'wp-content' in html_text or 'wp-includes' in html_text:
            signals["cms"].append("WordPress")
        if 'shopify' in html_text.lower():
            signals["cms"].append("Shopify")
        if 'wix' in html_text.lower():
            signals["cms"].append("Wix")
        
        # Analytics detection
        if 'gtag' in html_text or 'analytics.js' in html_text or 'GA_MEASUREMENT_ID' in html_text:
            signals["analytics"].append("Google Analytics")
        if 'mixpanel' in html_text.lower():
            signals["analytics"].append("Mixpanel")
        if 'segment' in html_text.lower() and 'analytics' in html_text.lower():
            signals["analytics"].append("Segment")
        
        # Frontend detection
        if 'react' in html_text.lower() or '__REACT_DEVTOOLS__' in html_text:
            signals["frontend"].append("React")
        if 'vue' in html_text.lower():
            signals["frontend"].append("Vue.js")
        if 'angular' in html_text.lower():
            signals["frontend"].append("Angular")
        if 'jquery' in html_text.lower():
            signals["frontend"].append("jQuery")
        
        # Marketing/CRM detection
        if 'hs-script-loader' in html_text or 'hubspotutk' in html_text:
            signals["marketing"].append("HubSpot")
        if 'munchkin' in html_text.lower():
            signals["marketing"].append("Marketo")
        if 'intercom' in html_text.lower():
            signals["marketing"].append("Intercom")
        
        # Remove empty categories
        return {k: v for k, v in signals.items() if v}

    @staticmethod
    def classify_location_type(address_text: str) -> str:
        """Classify location as HQ, Office, or Branch.
        
        Heuristics:
        - "Headquarters", "Registered Office" → HQ
        - "Branch Office", "Regional Office" → Branch
        - Default: Office
        
        Args:
            address_text: Address text to classify
            
        Returns:
            Location type: "HQ", "Office", or "Branch"
        """
        address_lower = address_text.lower()
        
        # HQ indicators
        if any(kw in address_lower for kw in ['headquarters', 'head office', 'registered office', 'main office', 'hq']):
            return "HQ"
        
        # Branch indicators
        if any(kw in address_lower for kw in ['branch', 'regional office', 'satellite office']):
            return "Branch"
        
        # Default
        return "Office"

    @staticmethod
    def extract_all_locations_with_types(text: str, domain: str = "") -> List[Dict[str, str]]:
        """Extract all locations and classify them.
        
        Returns list of dicts with:
        - address: Physical address
        - city: City
        - country: Country
        - type: HQ | Office | Branch
        
        First detected address is classified as HQ by default.
        """
        locations = []
        
        # Simple pattern: look for lines containing address keywords
        # operate on cleaned text to avoid html fragments
        cleaned_text = DeterministicExtractor._clean_fragment(text)
        lines = cleaned_text.split('\n')
        seen_addresses = set()
        
        for i, line in enumerate(lines):
            line_clean = line.strip()
            low = line_clean.lower()
            if any(kw in low for kw in ['address', 'office', 'location', 'headquarters', 'branch']):
                # Extract the address and next cleaned line if relevant
                address_text = line_clean
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if not any(kw in next_line.lower() for kw in ['email', 'phone', 'contact']):
                        address_text += f" {next_line}"

                address_text = DeterministicExtractor._clean_fragment(address_text)

                if address_text not in seen_addresses and len(address_text) > 5:
                    address, city, country = DeterministicExtractor.extract_address_parts(address_text)

                    # Classify location type
                    loc_type = DeterministicExtractor.classify_location_type(address_text)

                    # First location defaults to HQ
                    if not locations and loc_type == "Office":
                        loc_type = "HQ"

                    locations.append({
                        "address": address,
                        "city": city,
                        "country": country,
                        "type": loc_type
                    })
                    seen_addresses.add(address_text)
        
        return locations if locations else [{
            "address": "not_found",
            "city": "not_found",
            "country": "not_found",
            "type": "HQ"
        }]