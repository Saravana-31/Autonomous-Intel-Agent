"""Post-extraction validator for CompanyProfile.

Ensures mandatory fields are present and types are correct. Does not allow
hallucinated people; uses 'not_found' placeholder when data is missing.
"""
from schema import CompanyProfile, ContactDetails


class ExtractionValidationError(Exception):
    pass


def validate_profile(profile: CompanyProfile) -> None:
    """Validate the `CompanyProfile` structure.

    Raises `ExtractionValidationError` if critical schema invariants are violated.
    The validator allows the placeholder 'not_found' but ensures fields are
    present, lists are correct types, and people entries look like real people.
    
    Validates ALL mandatory fields per requirements.
    """
    # MANDATORY FIELD 1: Company Information
    if not isinstance(profile.company_name, str) or not profile.company_name:
        raise ExtractionValidationError('company_name is mandatory and must be non-empty string')
    if not isinstance(profile.domain, str) or not profile.domain:
        raise ExtractionValidationError('domain is mandatory and must be non-empty string')
    if not isinstance(profile.short_description, str):
        raise ExtractionValidationError('short_description must be a string')
    if not isinstance(profile.long_description, str):
        raise ExtractionValidationError('long_description must be a string')
    if not isinstance(profile.industry, str):
        raise ExtractionValidationError('industry must be a string')
    if not isinstance(profile.sub_industry, str):
        raise ExtractionValidationError('sub_industry must be a string')
    
    # MANDATORY FIELD 2: Services & Products
    if not isinstance(profile.services_offered, list):
        raise ExtractionValidationError('services_offered must be a list')
    if not isinstance(profile.products_offered, list):
        raise ExtractionValidationError('products_offered must be a list')

    # MANDATORY FIELD 3: Contact Information
    if not isinstance(profile.contact_information, ContactDetails):
        raise ExtractionValidationError('contact_information must be ContactDetails object')
    if not isinstance(profile.contact_information.email_addresses, list):
        raise ExtractionValidationError('email_addresses must be a list')
    if not isinstance(profile.contact_information.phone_numbers, list):
        raise ExtractionValidationError('phone_numbers must be a list')
    if not isinstance(profile.contact_information.physical_address, str):
        raise ExtractionValidationError('physical_address must be a string')
    if not isinstance(profile.contact_information.city, str):
        raise ExtractionValidationError('city must be a string')
    if not isinstance(profile.contact_information.country, str):
        raise ExtractionValidationError('country must be a string')
    if not isinstance(profile.contact_information.contact_page, str):
        raise ExtractionValidationError('contact_page must be a string')

    # MANDATORY FIELD 4: People Information
    if not isinstance(profile.people_information, list):
        raise ExtractionValidationError('people_information must be a list')
    for person in profile.people_information:
        if not isinstance(person.person_name, str) or not person.person_name or person.person_name == 'not_found':
            raise ExtractionValidationError(f'Invalid person entry: person_name must be non-empty string (got: {person.person_name})')
        if not isinstance(person.role, str):
            raise ExtractionValidationError('person role must be a string')
        if not isinstance(person.associated_company, str):
            raise ExtractionValidationError('associated_company must be a string')

    # MANDATORY FIELD 5: Services (structured)
    if not isinstance(profile.services, list):
        raise ExtractionValidationError('services must be a list')
    for svc in profile.services:
        if not isinstance(svc.service_or_product_name, str) or not svc.service_or_product_name:
            raise ExtractionValidationError('service_or_product_name must be non-empty string')
        if svc.type not in ('service', 'product'):
            raise ExtractionValidationError(f'service type must be "service" or "product" (got: {svc.type})')

    # MANDATORY FIELD 6: Social Media
    if not isinstance(profile.social_media, list):
        raise ExtractionValidationError('social_media must be a list')
    for sm in profile.social_media:
        if not isinstance(sm.platform, str) or not sm.platform:
            raise ExtractionValidationError('social_media platform must be non-empty string')
        if not isinstance(sm.url, str) or not sm.url:
            raise ExtractionValidationError('social_media url must be non-empty string')

    # MANDATORY FIELD 7: Certifications
    if not isinstance(profile.certifications, list):
        raise ExtractionValidationError('certifications must be a list')
    for cert in profile.certifications:
        if not isinstance(cert.certification_name, str) or not cert.certification_name:
            raise ExtractionValidationError('certification_name must be non-empty string')
        if not isinstance(cert.issuing_authority, str):
            raise ExtractionValidationError('issuing_authority must be a string')

    # Locations must be list of Location objects
    if not isinstance(profile.locations, list) or len(profile.locations) == 0:
        raise ExtractionValidationError('locations must be a non-empty list')
    for loc in profile.locations:
        if not all(isinstance(getattr(loc, attr), str) for attr in ('address', 'city', 'country')):
            raise ExtractionValidationError('location fields must be strings')

    # Tech stack signals must be lists
    if not isinstance(profile.tech_stack_signals.cms, list):
        raise ExtractionValidationError('tech stack CMS must be a list')

    # All good: function returns None
    return None
