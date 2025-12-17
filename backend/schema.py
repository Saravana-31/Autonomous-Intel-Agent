"""Pydantic schemas for company intelligence extraction."""

from typing import List, Optional
from pydantic import BaseModel, Field


class KeyPerson(BaseModel):
    """Schema for key personnel information."""
    name: str = Field(default="", description="Full name of the person")
    title: str = Field(default="", description="Job title")
    role_category: str = Field(default="", description="Category: executive, founder, manager, etc.")


class ContactInfo(BaseModel):
    """Schema for contact information."""
    email: Optional[str] = Field(default=None, description="Contact email")
    phone: Optional[str] = Field(default=None, description="Contact phone number")


class CompanyProfile(BaseModel):
    """Main schema for extracted company intelligence."""
    company_name: str = Field(default="", description="Official company name")
    description_short: str = Field(default="", description="Brief company description")
    industry: str = Field(default="", description="Primary industry")
    products_services: List[str] = Field(default_factory=list, description="Products or services offered")
    locations: List[str] = Field(default_factory=list, description="Office locations")
    key_people: List[KeyPerson] = Field(default_factory=list, description="Key personnel")
    contact: ContactInfo = Field(default_factory=ContactInfo, description="Contact information")
    tech_stack: List[str] = Field(default_factory=list, description="Technologies used")


class GraphNode(BaseModel):
    """Schema for knowledge graph node."""
    id: str = Field(description="Unique node identifier")
    type: str = Field(description="Node type: Company, Person, Location, Technology")
    label: str = Field(description="Display label")
    properties: dict = Field(default_factory=dict, description="Additional properties")


class GraphEdge(BaseModel):
    """Schema for knowledge graph edge."""
    source: str = Field(description="Source node ID")
    target: str = Field(description="Target node ID")
    relationship: str = Field(description="Relationship type: HAS_EMPLOYEE, LOCATED_IN, USES_TECH")


class KnowledgeGraph(BaseModel):
    """Schema for the complete knowledge graph."""
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)


class ProcessResponse(BaseModel):
    """API response schema."""
    profile: CompanyProfile
    graph: KnowledgeGraph
