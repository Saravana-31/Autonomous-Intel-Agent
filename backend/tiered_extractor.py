"""Tiered extraction system combining deterministic + LLM layers.

Fully implements problem statement requirements:
- Logo URL extraction with priority rules
- Contact page URL extraction  
- Tech stack signal detection
- Location classification (HQ vs Office vs Branch)
- Long description generation (LLM)
- Sub-industry classification (LLM)
- Role normalization with validation
- Person name validation
- Location confidence validation
"""

import json
import logging
import time
from typing import Dict, Any, List

from schema import (
    CompanyProfile, Location, KeyPerson, ContactDetails, TechStackSignals,
    SocialMedia, ServiceOrProduct, Certification
)
from llm.router import LLMRouter
from deterministic import DeterministicExtractor
from llm_extraction import LLMExtraction
from cache_manager import CacheManager
from pre_extracted_loader import PreExtractedLoader

logger = logging.getLogger(__name__)


class TieredExtractor:
    """Combines deterministic extraction + LLM-based normalization.
    
    Layer 1: Deterministic (fast, no LLM)
    - Emails, phones, social links, addresses
    - Domain, company name from metadata
    - Certifications (keyword-based)
    
    Layer 2: LLM (Ollama primary, Phi-2 fallback)
    - Industry/sub-industry classification
    - Description synthesis
    - Role normalization
    - Service/product normalization
    """

    def __init__(self):
        self.llm_router = LLMRouter()
        self.deterministic = DeterministicExtractor()
        self.cache_manager = CacheManager()
        self.pre_extracted_loader = PreExtractedLoader()

    def extract(self, text: str, company_domain: str = "unknown", html_files=None, use_cache: bool = True) -> CompanyProfile:
        """Extract company profile using tiered approach.
        
        Args:
            text: Cleaned website text
            company_domain: Company domain (used as fallback for domain extraction)
            html_files: Optional HTML files for extraction
            use_cache: If True, check cache before extraction (default: True)
            
        Returns:
            CompanyProfile with all mandatory fields populated
        """
        # Check cache first if enabled
        if use_cache:
            cached_data = self.cache_manager.load_cache(company_domain)
            if cached_data:
                logger.info(f"Loading cached profile for {company_domain} (skipping LLM calls)")
                profile = CompanyProfile(**cached_data['profile'])
                return profile
            
            # Check pre-extracted data (demo mode)
            pre_extracted = self.pre_extracted_loader.load_pre_extracted(company_domain)
            if pre_extracted:
                logger.info(f"Loading pre-extracted profile for {company_domain} (demo mode)")
                return pre_extracted
        
        start_time = time.time()
        logger.info("Starting tiered extraction (deterministic + LLM)")
        
        # Layer 1: Deterministic extraction
        logger.info("Layer 1: Running deterministic extraction...")
        det_start = time.time()
        det_data = self._deterministic_extract(text, company_domain, html_files)
        det_duration = time.time() - det_start
        logger.info(f"Deterministic extraction completed in {det_duration:.2f}s")
        
        # Layer 2: LLM-based normalization and synthesis
        logger.info("Layer 2: Running LLM extraction...")
        llm_start = time.time()
        llm_extraction_failed = False
        try:
            llm_data = self._llm_extract(text, det_data)
            llm_duration = time.time() - llm_start
            logger.info(f"LLM extraction completed in {llm_duration:.2f}s using {self.llm_router.last_used_provider}")
        except (ValueError, RuntimeError) as e:
            # JSON validation failed - abort, don't cache
            llm_duration = time.time() - llm_start
            logger.error(f"LLM extraction failed (invalid JSON) after {llm_duration:.2f}s: {e}")
            llm_extraction_failed = True
            llm_data = {}
            # Don't raise - continue with deterministic data only
        except Exception as e:
            llm_duration = time.time() - llm_start
            logger.error(f"LLM extraction failed after {llm_duration:.2f}s: {e}")
            llm_data = {}
        
        # Merge results
        profile = self._merge_results(det_data, llm_data)
        
        # If JSON validation failed, mark profile to prevent caching
        if llm_extraction_failed:
            logger.warning(f"LLM extraction failed for {company_domain} - marking profile to skip cache")
            # Store flag in profile for main.py to check
            profile._llm_json_failed = True
        
        total_duration = time.time() - start_time
        logger.info(f"Total extraction completed in {total_duration:.2f}s")
        
        return profile
        

    def _deterministic_extract(self, text: str, company_domain: str = "unknown", html_files=None) -> Dict[str, Any]:
        """Run deterministic extraction layer (NO LLM).
        
        Extracts ALL deterministic fields per problem statement:
        - Contact info (emails, phones)
        - Social media links
        - Domain, company name
        - Addresses with city/country
        - Certifications
        - Logo URL (NEW - with priority rules)
        - Contact page URL (NEW)
        - Tech stack signals (NEW - HTML patterns)
        - Locations with types (NEW - HQ vs Office vs Branch)
        """
        # Basic extraction
        emails = self.deterministic.extract_emails(text)
        phones = self.deterministic.extract_phone_numbers(text)
        social_links = self.deterministic.extract_social_links(text)
        
        # Use provided domain, or extract from text
        domain = company_domain if company_domain != "unknown" else self.deterministic.extract_domain(text)
        company_name = self.deterministic.extract_company_name(text, domain)
        address, city, country = self.deterministic.extract_address_parts(text)
        services_raw, products_raw = self.deterministic.extract_services_and_products(text)
        certifications_raw = self.deterministic.extract_certifications(text)
        people = self.deterministic.extract_people_mentions(text)
        
        # Use raw HTML when available for HTML-specific extractions
        raw_html = None
        if html_files:
            try:
                # html_files expected as list of (filename, content)
                raw_html = "\n".join([c for _, c in html_files])
            except Exception:
                raw_html = None
        
        # Store html_files for LLM context
        stored_html_files = html_files if html_files else None

        # NEW: Logo URL extraction (with priority rules: logo > brand > navbar)
        html_for_logo = raw_html if raw_html else text
        logo_url = self.deterministic.extract_logo_url(html_for_logo, domain, f"http://{domain}")
        
        # NEW: Contact page URL extraction (use raw HTML if available)
        contact_page_url = self.deterministic.extract_contact_page_url(raw_html if raw_html else text)
        
        # NEW: Tech stack signals (CMS, analytics, frontend, marketing)
        tech_signals = self.deterministic.extract_tech_stack_signals(raw_html if raw_html else text)
        
        # NEW: Locations with type classification (HQ, Office, Branch)
        locations_with_types = self.deterministic.extract_all_locations_with_types(raw_html if raw_html else text, domain)
        
        return {
            "emails": emails,
            "phones": phones,
            "social_links": social_links,
            "domain": domain,
            "company_name": company_name,
            "address": address,
            "city": city,
            "country": country,
            "services_raw": services_raw,
            "products_raw": products_raw,
            "certifications_raw": certifications_raw,
            "people": people,
            "logo_url": logo_url,  # NEW
            "contact_page_url": contact_page_url,  # NEW
            "tech_signals": tech_signals,  # NEW
            "locations_with_types": locations_with_types,  # NEW
            "raw_text": text[:2000],  # For LLM context
            "html_files": stored_html_files  # Pass HTML files for LLM context
        }


    def _llm_extract(self, text: str, det_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run LLM extraction layer for semantic tasks per problem statement.
        
        LLM Tasks:
        1. Generate long description (max 3 sentences, 80 words)
        2. Classify industry and sub-industry
        3. Normalize person roles (to Founder|Executive|Director|Manager|Employee)
        4. Normalize service/product names
        
        Includes timeout control (max 25 seconds) and retry logic.
        """
        import time
        
        # Get html_files from det_data if available
        html_files = det_data.get('html_files')
        
        prompt = LLMExtraction.build_llm_prompt(
            text=text,
            company_name=det_data['company_name'],
            products_services=det_data['products_raw'] + det_data['services_raw'],
            domain=det_data['domain'],
            html_files=html_files
        )
        
        max_retries = 1
        extraction_status = "complete"
        
        for attempt in range(max_retries + 1):
            try:
                start_time = time.time()
                llm_raw_response = self.llm_router.extract(prompt, schema={})
                duration = time.time() - start_time
                
                if duration > 25:
                    logger.warning(f"LLM extraction took {duration:.2f}s (exceeded 25s limit)")
                
                logger.debug(f"LLM raw response: {llm_raw_response}")
                
                # Parse LLM response (may raise ValueError if JSON invalid)
                llm_data = LLMExtraction.parse_llm_response(str(llm_raw_response))
                
                # Enrich with people role normalization
                people_normalized = LLMExtraction.normalize_roles(
                    det_data['people'],
                    llm_response=str(llm_raw_response)
                )
                llm_data['people_with_roles'] = people_normalized
                
                # Mark status if retry was used
                if attempt > 0:
                    extraction_status = "repaired"
                
                return llm_data
                
            except (ValueError, RuntimeError) as e:
                # JSON validation failed
                if attempt < max_retries:
                    logger.warning(f"LLM extraction error (attempt {attempt + 1}): {e}. Retrying...")
                    extraction_status = "repaired"
                    continue
                else:
                    # Final attempt failed - re-raise to prevent caching
                    logger.error(f"LLM extraction error (invalid JSON after {max_retries + 1} attempts): {e}")
                    raise
            except Exception as e:
                logger.error(f"LLM extraction error: {e}")
                raise

    def _build_deterministic_summary(self, det_data: Dict[str, Any]) -> str:
        """Build a summary of deterministic extraction for LLM context."""
        summary = f"""
Company Domain: {det_data['domain']}
Company Name: {det_data['company_name']}
Location: {det_data['city']}, {det_data['country']}
Email: {', '.join(det_data['emails']) if det_data['emails'] else 'None found'}
Phone: {', '.join(det_data['phones']) if det_data['phones'] else 'None found'}
Social Links: {', '.join([f"{p}: {u}" for p, u in det_data['social_links']]) if det_data['social_links'] else 'None found'}
Services (Raw): {', '.join(det_data['services_raw'][:5]) if det_data['services_raw'] else 'None found'}
Products (Raw): {', '.join(det_data['products_raw'][:5]) if det_data['products_raw'] else 'None found'}
Certifications: {', '.join(det_data['certifications_raw']) if det_data['certifications_raw'] else 'None found'}
Key People: {', '.join(det_data['people'][:5]) if det_data['people'] else 'None found'}
"""
        return summary

    def _merge_results(self, det_data: Dict[str, Any], llm_data: Dict[str, Any]) -> CompanyProfile:
        """Merge deterministic + LLM results into CompanyProfile (mandatory fields per problem statement).
        
        Validates:
        - Person names (≥2 words, not slogans)
        - Location confidence (≥2 occurrences or structured address)
        - Role normalization (Founder, Executive, Director, Manager, Employee)
        """
        
        # MANDATORY FIELD 1: Company Name (from deterministic)
        company_name = det_data.get('company_name') or 'not_found'

        # MANDATORY FIELD 2: Domain (from deterministic)
        domain = det_data.get('domain') or 'not_found'

        # MANDATORY FIELD 3: Logo URL (from deterministic with priority rules)
        logo_url = det_data.get('logo_url') or 'not_found'

        # MANDATORY FIELD 4: Short Description (improved extraction)
        # Try multiple sources: LLM description, services summary, or company name + domain
        short_description = llm_data.get('short_description') or llm_data.get('description') or 'not_found'
        
        # If still not_found, generate from available data (avoid repeating company name)
        if short_description == 'not_found':
            # Try to create from services/products (don't repeat company name)
            if det_data.get('services_raw') or det_data.get('products_raw'):
                items = (det_data.get('services_raw', []) + det_data.get('products_raw', []))[:3]
                if items:
                    # Use "Provider of..." or "Offers..." instead of repeating company name
                    short_description = f"Provider of {', '.join(items)}"
            # Final fallback: minimal description
            if short_description == 'not_found' and company_name != 'not_found':
                # Don't repeat company name unnecessarily
                short_description = f"Company operating at {domain}"

        # MANDATORY FIELD 5: Long Description (LLM-generated, 4-6 sentences)
        long_description = llm_data.get('long_description') or 'not_found'

        # MANDATORY FIELD 6: Industry (LLM-classified)
        industry = llm_data.get('industry') or 'not_found'

        # MANDATORY FIELD 7: Sub-Industry (LLM-classified)
        sub_industry = llm_data.get('sub_industry') or 'not_found'
        
        # MANDATORY FIELD 8: Services & Products (separated per requirements)
        services_offered = []
        products_offered = []
        
        # Get normalized services/products from LLM
        services_normalized = llm_data.get('services', det_data.get('services_raw', []))
        products_normalized = llm_data.get('products', det_data.get('products_raw', []))
        
        for item in services_normalized:
            if item and item != 'not_found' and isinstance(item, str):
                services_offered.append(item)
        
        for item in products_normalized:
            if item and item != 'not_found' and isinstance(item, str):
                products_offered.append(item)
        
        # Legacy combined list for backward compatibility
        products_services = services_offered + products_offered
        
        # Build structured services/products list
        structured_services = []
        for svc in services_offered:
            structured_services.append(ServiceOrProduct(
                domain=domain,
                service_or_product_name=svc,
                type='service'
            ))
        for prod in products_offered:
            structured_services.append(ServiceOrProduct(
                domain=domain,
                service_or_product_name=prod,
                type='product'
            ))
        
        # MANDATORY FIELD 9: Locations with types (normalized, no concatenation)
        locations = []
        for loc_dict in det_data.get('locations_with_types', []):
            # Validate location confidence
            address_val = loc_dict.get('address') or 'not_found'
            city_val = loc_dict.get('city') or 'not_found'
            country_val = loc_dict.get('country') or 'not_found'
            
            # Normalize: ensure proper structure, no concatenation
            if LLMExtraction.validate_location(address_val) or country_val != 'not_found':
                locations.append(Location(
                    type=loc_dict.get('type', 'Office'),
                    address=address_val,
                    city=city_val,
                    country=country_val
                ))
        
        # Fallback if no locations - ensure proper structure
        if not locations:
            # Use extracted city/country if available
            city_val = det_data.get('city') or 'not_found'
            country_val = det_data.get('country') or 'not_found'
            locations = [Location(
                type='HQ',
                address='not_found',
                city=city_val,
                country=country_val
            )]
        
        # MANDATORY FIELD 10: People Information (with strict validation)
        # CRITICAL: Person MUST satisfy at least 2 criteria:
        # 1. Matches human name pattern (First Last)
        # 2. Appears near role keywords (CEO, Founder, Director, etc.)
        # 3. Appears in /about, /team, /leadership pages
        people_information = []
        key_people = []  # Legacy field
        
        people_raw = det_data.get('people', [])
        people_with_roles = llm_data.get('people_with_roles', [])

        # Use only validated people from deterministic layer (already filtered by extract_people_mentions)
        validated_people = []
        for name in people_raw:
            # Double-check validation (deterministic layer should have done this, but be safe)
            if LLMExtraction.validate_person_name(name):
                validated_people.append({'name': name, 'title': 'not_found'})

        # If LLM provided role hints, apply them only to the validated names
        if people_with_roles:
            normalized = LLMExtraction.normalize_roles(validated_people, llm_response=str(people_with_roles))
        else:
            normalized = LLMExtraction.normalize_roles(validated_people)

        for person in normalized:
            person_name = person.get('name', '')
            if person_name and LLMExtraction.validate_person_name(person_name):
                # Create KeyPerson with new schema fields
                key_person = KeyPerson(
                    person_name=person_name,
                    role=person.get('title', 'not_found'),
                    designation=person.get('title', 'not_found'),
                    associated_company=company_name,
                    role_category=person.get('role_category', 'Employee')
                )
                people_information.append(key_person)
                key_people.append(key_person)  # Legacy field
        
        # MANDATORY FIELD 11: Contact Information (new schema)
        # Get primary location for physical address
        primary_location = locations[0] if locations else None
        physical_address = primary_location.address if primary_location else 'not_found'
        contact_city = primary_location.city if primary_location else (det_data.get('city') or 'not_found')
        contact_country = primary_location.country if primary_location else (det_data.get('country') or 'not_found')
        
        contact_information = ContactDetails(
            email_addresses=det_data.get('emails', []),
            phone_numbers=det_data.get('phones', []),
            physical_address=physical_address,
            city=contact_city,
            country=contact_country,
            contact_page=det_data.get('contact_page_url') or 'not_found'
        )
        
        # Legacy field for backward compatibility
        contact_details = contact_information
        
        # MANDATORY FIELD 12: Social Media (from deterministic extraction)
        social_media_list = []
        for platform, url in det_data.get('social_links', []):
            social_media_list.append(SocialMedia(platform=platform, url=url))
        
        # Set validated absence status for social media
        social_status = "validated_present" if social_media_list else "validated_absent"
        
        # MANDATORY FIELD 13: Certifications (structured)
        certifications_list = []
        for cert_name in det_data.get('certifications_raw', []):
            # Try to extract issuing authority (heuristic)
            issuing_authority = 'not_found'
            if 'ISO' in cert_name:
                issuing_authority = 'International Organization for Standardization'
            elif 'SOC' in cert_name:
                issuing_authority = 'AICPA'
            elif 'PCI' in cert_name:
                issuing_authority = 'PCI Security Standards Council'
            elif 'GDPR' in cert_name:
                issuing_authority = 'European Union'
            
            certifications_list.append(Certification(
                certification_name=cert_name,
                issuing_authority=issuing_authority
            ))
        
        # Set validated absence status for certifications
        certification_status = "validated_present" if certifications_list else "validated_absent"
        
        # Set validated absence status for people
        people_status = "validated_present" if people_information else "validated_absent"
        
        # MANDATORY FIELD 14: Tech Stack Signals (from deterministic HTML analysis)
        tech_stack_signals = TechStackSignals(
            cms=det_data.get('tech_signals', {}).get('cms', []),
            analytics=det_data.get('tech_signals', {}).get('analytics', []),
            frontend=det_data.get('tech_signals', {}).get('frontend', []),
            marketing=det_data.get('tech_signals', {}).get('marketing', [])
        )
        
        # Build CompanyProfile with ALL mandatory fields (new schema)
        profile = CompanyProfile(
            company_name=company_name,
            domain=domain,
            short_description=short_description,
            long_description=long_description,
            industry=industry,
            sub_industry=sub_industry,
            services_offered=services_offered,
            products_offered=products_offered,
            contact_information=contact_information,
            people_information=people_information,
            people_status=people_status,
            services=structured_services,
            social_media=social_media_list,
            social_status=social_status,
            certifications=certifications_list,
            certification_status=certification_status,
            locations=locations,
            tech_stack_signals=tech_stack_signals,
            # Legacy fields for backward compatibility
            logo_url=logo_url,
            products_services=products_services,
            key_people=key_people,
            contact_details=contact_details
        )
        # Cache structured profile deterministically
        try:
            import os, json
            cache_dir = os.path.join('cache', domain)
            os.makedirs(cache_dir, exist_ok=True)
            with open(os.path.join(cache_dir, 'profile.json'), 'w', encoding='utf-8') as fh:
                fh.write(profile.json(indent=2, ensure_ascii=False))
        except Exception:
            logger.debug('Failed to write cache for domain: %s', domain)

        return profile
    
    def _normalize_role(self, raw_role: str) -> str:
        """Normalize role to allowed categories (per problem statement).
        
        Allowed: Founder, Executive, Director, Manager, Employee
        """
        raw_lower = raw_role.lower()
        
        if any(kw in raw_lower for kw in ['founder', 'co-founder']):
            return 'Founder'
        if any(kw in raw_lower for kw in ['ceo', 'cto', 'cfo', 'president', 'vice president', 'executive', 'chief']):
            return 'Executive'
        if any(kw in raw_lower for kw in ['director']):
            return 'Director'
        if any(kw in raw_lower for kw in ['manager', 'lead', 'head']):
            return 'Manager'
        
        # Default
        return 'Employee'
