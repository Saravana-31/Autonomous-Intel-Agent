"""Pydantic schemas for company intelligence extraction.

Implements tiered extraction architecture with mandatory field enforcement.
All schemas match the exact problem statement requirements.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# --- Mandatory Location Schema ---

class Location(BaseModel):
    """Mandatory location information."""
    type: str = Field(default="Office", description="HQ | Office | Branch")
    address: str = Field(default="not_found", description="Physical address")
    city: str = Field(default="not_found", description="City")
    country: str = Field(default="not_found", description="Country")


# --- Mandatory Key Person Schema ---

class KeyPerson(BaseModel):
    """Mandatory key person information."""
    person_name: str = Field(default="not_found", description="Full name of the person")
    role: str = Field(default="not_found", description="Job title/designation")
    designation: str = Field(default="not_found", description="Alternative role field")
    associated_company: str = Field(default="not_found", description="Company name")
    role_category: str = Field(default="Employee", description="Founder | Executive | Director | Manager | Employee")


# --- Mandatory Contact Details Schema ---

class ContactDetails(BaseModel):
    """Mandatory contact information."""
    email_addresses: List[str] = Field(default_factory=list, description="Email addresses")
    phone_numbers: List[str] = Field(default_factory=list, description="Phone numbers")
    physical_address: str = Field(default="not_found", description="Physical address")
    country: str = Field(default="not_found", description="Country")
    city: str = Field(default="not_found", description="City")
    contact_page: str = Field(default="not_found", description="Contact page URL")


# --- Social Media Schema ---

class SocialMedia(BaseModel):
    """Social media link."""
    platform: str = Field(description="Platform name (LinkedIn, Twitter, etc.)")
    url: str = Field(description="Social media URL")


# --- Service/Product Schema ---

class ServiceOrProduct(BaseModel):
    """Service or product offering."""
    domain: str = Field(default="not_found", description="Company domain")
    service_or_product_name: str = Field(description="Name of service or product")
    type: str = Field(description="'service' or 'product'")


# --- Certification Schema ---

class Certification(BaseModel):
    """Certification information."""
    certification_name: str = Field(description="Name of certification")
    issuing_authority: str = Field(default="not_found", description="Issuing authority")


# --- Mandatory Tech Stack Signals Schema ---

class TechStackSignals(BaseModel):
    """Tech stack signals detected from HTML."""
    cms: List[str] = Field(default_factory=list, description="CMS platforms")
    analytics: List[str] = Field(default_factory=list, description="Analytics tools")
    frontend: List[str] = Field(default_factory=list, description="Frontend frameworks")
    marketing: List[str] = Field(default_factory=list, description="Marketing platforms")


# --- MANDATORY COMPANY PROFILE (Problem Statement Required) ---

class CompanyProfile(BaseModel):
    """Main schema matching exact problem statement requirements."""
    
    # Section 1: Basic Company Information (MANDATORY)
    company_name: str = Field(default="not_found", description="Official company name")
    domain: str = Field(default="not_found", description="Company domain/website")
    short_description: str = Field(default="not_found", description="Brief company description")
    long_description: str = Field(default="not_found", description="Detailed company description (LLM-generated)")
    industry: str = Field(default="not_found", description="Primary industry (LLM-normalized)")
    sub_industry: str = Field(default="not_found", description="Sub-industry classification (LLM-classified)")
    services_offered: List[str] = Field(default_factory=list, description="Services offered")
    products_offered: List[str] = Field(default_factory=list, description="Products offered")
    
    # Section 2: Contact Information (MANDATORY)
    contact_information: ContactDetails = Field(default_factory=ContactDetails, description="Contact information")
    
    # Section 3: People Information (MANDATORY)
    people_information: List[KeyPerson] = Field(default_factory=list, description="Key personnel")
    people_status: str = Field(default="validated_absent", description="Status: validated_present | validated_absent")
    
    # Section 4: Services (structured)
    services: List[ServiceOrProduct] = Field(default_factory=list, description="Structured services/products")
    
    # Section 5: Social Media
    social_media: List[SocialMedia] = Field(default_factory=list, description="Social media links")
    social_status: str = Field(default="validated_absent", description="Status: validated_present | validated_absent")
    
    # Section 6: Certifications
    certifications: List[Certification] = Field(default_factory=list, description="Certifications")
    certification_status: str = Field(default="validated_absent", description="Status: validated_present | validated_absent")
    
    # Section 7: Locations
    locations: List[Location] = Field(default_factory=lambda: [
        Location(type="HQ", address="not_found", city="not_found", country="not_found")
    ], description="Locations with type classification")
    
    # Section 8: Tech Stack (optional)
    tech_stack_signals: TechStackSignals = Field(default_factory=TechStackSignals, description="Detected technologies")
    
    # Legacy fields for backward compatibility (deprecated)
    logo_url: str = Field(default="not_found", description="Logo image URL (legacy)")
    products_services: List[str] = Field(default_factory=list, description="Legacy combined list")
    key_people: List[KeyPerson] = Field(default_factory=list, description="Legacy people list")
    contact_details: ContactDetails = Field(default_factory=ContactDetails, description="Legacy contact")


# --- KNOWLEDGE GRAPH SCHEMAS (Do Not Change Structure) ---

class GraphNode(BaseModel):
    """Schema for knowledge graph node."""
    id: str = Field(description="Unique node identifier")
    type: str = Field(description="Node type: Company, Person, Product/Service, Location, Certification, Tech")
    label: str = Field(description="Display label")
    properties: dict = Field(default_factory=dict, description="Additional properties")


class GraphEdge(BaseModel):
    """Schema for knowledge graph edge."""
    source: str = Field(description="Source node ID")
    target: str = Field(description="Target node ID")
    relationship: str = Field(description="Relationship type: OFFERS, EMPLOYS, LOCATED_AT, HAS_CERTIFICATION, USES_TECH")


class KnowledgeGraph(BaseModel):
    """Schema for the complete knowledge graph."""
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)


# --- API RESPONSE ---

class ProcessResponse(BaseModel):
    """API response with company profile and knowledge graph."""
    profile: CompanyProfile
    graph: KnowledgeGraph
    llm_engine_used: str = Field(default="unknown", description="LLM provider used: 'Ollama'")


