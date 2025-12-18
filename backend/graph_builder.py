"""Knowledge graph builder from company profile.

Deterministically generates graph from extracted JSON.
Graph structure per problem statement:
- Nodes: Company, Person, Product/Service, Location
- Edges: OFFERS, EMPLOYS, LOCATED_AT
"""

from typing import List
from schema import CompanyProfile, KnowledgeGraph, GraphNode, GraphEdge


class GraphBuilder:
    """Builds deterministic knowledge graph from company profile."""
    
    def build(self, profile: CompanyProfile) -> KnowledgeGraph:
        """Build knowledge graph from extracted company profile.
        
        Nodes:
        - Company (root)
        - Person (from key_people)
        - Product/Service (from products_services)
        - Location (from locations)
        
        Edges:
        - EMPLOYS: Company → Person
        - OFFERS: Company → Product/Service
        - LOCATED_AT: Company → Location
        
        Args:
            profile: Extracted company profile
            
        Returns:
            KnowledgeGraph with nodes and edges
        """
        nodes: List[GraphNode] = []
        edges: List[GraphEdge] = []
        
        # 1. Create company node (root)
        company_id = self._make_id("company", profile.company_name or "company")
        company_label = profile.company_name if profile.company_name != "not_found" else "Not Found Company"
        nodes.append(GraphNode(
            id=company_id,
            type="Company",
            label=company_label,
            properties={
                "domain": profile.domain,
                "industry": profile.industry,
                "sub_industry": profile.sub_industry,
                "short_description": profile.short_description,
            }
        ))
        
        # 2. Add person nodes with EMPLOYS edges (from people_information)
        # Use new schema field first, fallback to legacy key_people
        people_list = getattr(profile, 'people_information', []) or getattr(profile, 'key_people', [])
        for i, person in enumerate(people_list):
            # Only create Person nodes for validated people
            person_name = getattr(person, 'person_name', None) or getattr(person, 'name', None)
            if not person_name or person_name == "not_found":
                continue

            person_id = self._make_id("person", f"{person_name}_{i}")
            person_title = getattr(person, 'role', None) or getattr(person, 'title', 'not_found')
            role_category = getattr(person, 'role_category', 'Employee')
            
            nodes.append(GraphNode(
                id=person_id,
                type="Person",
                label=person_name,
                properties={
                    "title": person_title if person_title != 'not_found' else '',
                    "role_category": role_category
                }
            ))

            # EMPLOYS edge
            edges.append(GraphEdge(
                source=company_id,
                target=person_id,
                relationship="EMPLOYS"
            ))
        
        # 3. Add product/service nodes with OFFERS edges (from structured services)
        # Use new schema field first, fallback to legacy products_services
        services_list = getattr(profile, 'services', []) or []
        products_services_legacy = getattr(profile, 'products_services', []) or []
        
        # Process structured services/products
        for i, svc in enumerate(services_list):
            if not svc.service_or_product_name or svc.service_or_product_name == "not_found":
                continue

            product_id = self._make_id("product", f"{svc.service_or_product_name}_{i}")
            nodes.append(GraphNode(
                id=product_id,
                type="Product/Service",
                label=svc.service_or_product_name,
                properties={
                    "type": svc.type
                }
            ))

            # OFFERS edge
            edges.append(GraphEdge(
                source=company_id,
                target=product_id,
                relationship="OFFERS"
            ))
        
        # Fallback to legacy products_services if structured list is empty
        if not services_list:
            for i, product in enumerate(products_services_legacy):
                if not product or product == "not_found":
                    continue

                product_id = self._make_id("product", f"{product}_{i}")
                nodes.append(GraphNode(
                    id=product_id,
                    type="Product/Service",
                    label=product,
                    properties={}
                ))

                # OFFERS edge
                edges.append(GraphEdge(
                    source=company_id,
                    target=product_id,
                    relationship="OFFERS"
                ))
        
        # 4. Add location nodes with LOCATED_AT edges
        for i, location in enumerate(profile.locations):
            if not location.address or location.address == "not_found":
                continue

            location_label = f"{location.city}, {location.country}" if location.city and location.city != "not_found" else location.address
            location_id = self._make_id("location", f"{location_label}_{i}")

            nodes.append(GraphNode(
                id=location_id,
                type="Location",
                label=location_label,
                properties={
                    "type": location.type,
                    "address": location.address,
                    "city": location.city,
                    "country": location.country
                }
            ))

            # LOCATED_AT edge
            edges.append(GraphEdge(
                source=company_id,
                target=location_id,
                relationship="LOCATED_AT"
            ))

        # 5. Add certification nodes and HAS_CERTIFICATION edges (if any)
        # Handle both new Certification objects and legacy string list
        certifications_list = getattr(profile, 'certifications', []) or []
        for i, cert in enumerate(certifications_list):
            # Handle both Certification objects and strings
            if isinstance(cert, str):
                cert_name = cert
                if not cert_name or cert_name == 'not_found':
                    continue
            else:
                # Certification object
                cert_name = getattr(cert, 'certification_name', None)
                if not cert_name or cert_name == 'not_found':
                    continue
            
            cert_id = self._make_id('cert', f"{cert_name}_{i}")
            nodes.append(GraphNode(
                id=cert_id,
                type='Certification',
                label=cert_name,
                properties={
                    "issuing_authority": getattr(cert, 'issuing_authority', 'not_found') if not isinstance(cert, str) else 'not_found'
                }
            ))
            edges.append(GraphEdge(
                source=company_id,
                target=cert_id,
                relationship='HAS_CERTIFICATION'
            ))
        
        # 6. Add tech stack nodes with USES_TECH edges
        tech_stack = getattr(profile, 'tech_stack_signals', None)
        if tech_stack:
            all_tech = []
            all_tech.extend(getattr(tech_stack, 'cms', []) or [])
            all_tech.extend(getattr(tech_stack, 'analytics', []) or [])
            all_tech.extend(getattr(tech_stack, 'frontend', []) or [])
            all_tech.extend(getattr(tech_stack, 'marketing', []) or [])
            
            seen_tech = set()
            for tech in all_tech:
                if tech and tech not in seen_tech:
                    seen_tech.add(tech)
                    tech_id = self._make_id('tech', tech)
                    nodes.append(GraphNode(
                        id=tech_id,
                        type='Tech',
                        label=tech,
                        properties={}
                    ))
                    edges.append(GraphEdge(
                        source=company_id,
                        target=tech_id,
                        relationship='USES_TECH'
                    ))
        
        return KnowledgeGraph(nodes=nodes, edges=edges)
    
    def _make_id(self, prefix: str, name: str) -> str:
        """Create deterministic ID from prefix and name."""
        clean_name = "".join(c if c.isalnum() else "_" for c in name.lower())[:50]
        return f"{prefix}_{clean_name}".replace('__', '_')
