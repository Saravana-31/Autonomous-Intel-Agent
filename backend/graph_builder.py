"""Knowledge graph builder from company profile."""

from typing import List
from schema import CompanyProfile, KnowledgeGraph, GraphNode, GraphEdge


class GraphBuilder:
    """Builds a knowledge graph from company profile data."""
    
    def build(self, profile: CompanyProfile) -> KnowledgeGraph:
        """
        Build knowledge graph from company profile.
        
        Args:
            profile: Extracted company profile
            
        Returns:
            KnowledgeGraph with nodes and edges
        """
        nodes: List[GraphNode] = []
        edges: List[GraphEdge] = []
        
        # Create company node
        company_id = self._make_id("company", profile.company_name or "unknown")
        nodes.append(GraphNode(
            id=company_id,
            type="Company",
            label=profile.company_name or "Unknown Company",
            properties={
                "description": profile.description_short,
                "industry": profile.industry
            }
        ))
        
        # Add person nodes and edges
        for i, person in enumerate(profile.key_people):
            if not person.name:
                continue
                
            person_id = self._make_id("person", f"{person.name}_{i}")
            nodes.append(GraphNode(
                id=person_id,
                type="Person",
                label=person.name,
                properties={
                    "title": person.title,
                    "role_category": person.role_category
                }
            ))
            edges.append(GraphEdge(
                source=company_id,
                target=person_id,
                relationship="HAS_EMPLOYEE"
            ))
        
        # Add location nodes and edges
        for i, location in enumerate(profile.locations):
            if not location:
                continue
                
            location_id = self._make_id("location", f"{location}_{i}")
            nodes.append(GraphNode(
                id=location_id,
                type="Location",
                label=location,
                properties={}
            ))
            edges.append(GraphEdge(
                source=company_id,
                target=location_id,
                relationship="LOCATED_IN"
            ))
        
        # Add technology nodes and edges
        for i, tech in enumerate(profile.tech_stack):
            if not tech:
                continue
                
            tech_id = self._make_id("tech", f"{tech}_{i}")
            nodes.append(GraphNode(
                id=tech_id,
                type="Technology",
                label=tech,
                properties={}
            ))
            edges.append(GraphEdge(
                source=company_id,
                target=tech_id,
                relationship="USES_TECH"
            ))
        
        # Add product/service nodes
        for i, product in enumerate(profile.products_services):
            if not product:
                continue
                
            product_id = self._make_id("product", f"{product}_{i}")
            nodes.append(GraphNode(
                id=product_id,
                type="Product",
                label=product,
                properties={}
            ))
            edges.append(GraphEdge(
                source=company_id,
                target=product_id,
                relationship="OFFERS"
            ))
        
        return KnowledgeGraph(nodes=nodes, edges=edges)
    
    def _make_id(self, prefix: str, name: str) -> str:
        """Create a clean ID from prefix and name."""
        clean_name = "".join(c if c.isalnum() else "_" for c in name.lower())
        return f"{prefix}_{clean_name}"
