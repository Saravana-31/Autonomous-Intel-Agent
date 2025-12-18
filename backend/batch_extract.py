"""Batch extraction script for processing multiple company domains.

Processes all available company snapshots and saves structured profiles
to backend/data/extracted_profiles/domain.json

Usage:
    python batch_extract.py
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

from loader import HTMLLoader
from cleaner import HTMLCleaner
from tiered_extractor import TieredExtractor
from graph_builder import GraphBuilder
from post_extraction_validator import validate_profile, ExtractionValidationError
from schema import ProcessResponse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BatchExtractor:
    """Batch processor for multiple company domains."""
    
    def __init__(self):
        self.loader = HTMLLoader(data_dir="data")
        self.cleaner = HTMLCleaner()
        self.extractor = TieredExtractor()
        self.graph_builder = GraphBuilder()
        self.output_dir = Path("data/extracted_profiles")
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def process_domain(self, domain: str) -> Dict[str, Any]:
        """Process a single domain and return results.
        
        Args:
            domain: Company domain name
            
        Returns:
            Dict with success status, profile, graph, and any errors
        """
        logger.info(f"Processing domain: {domain}")
        
        try:
            # Load HTML files
            html_files = self.loader.load_html_files(domain)
            logger.info(f"Loaded {len(html_files)} HTML files for {domain}")
            
            # Clean and concatenate text
            cleaned_text = self.cleaner.process_files(html_files)
            truncated_text = self.cleaner.truncate_text(cleaned_text, max_chars=2500)
            logger.info(f"Cleaned text length: {len(truncated_text)} chars")
            
            # Extract company profile
            logger.info("Starting tiered extraction...")
            profile = self.extractor.extract(
                truncated_text,
                company_domain=domain,
                html_files=html_files
            )
            logger.info(f"Extracted profile for: {profile.company_name}")
            
            # Validate profile
            try:
                validate_profile(profile)
                logger.info(f"Profile validation passed for {domain}")
            except ExtractionValidationError as e:
                logger.error(f"Profile validation failed for {domain}: {e}")
                return {
                    "success": False,
                    "domain": domain,
                    "error": f"Validation error: {e}",
                    "profile": None,
                    "graph": None
                }
            
            # Build knowledge graph
            graph = self.graph_builder.build(profile)
            logger.info(f"Built graph with {len(graph.nodes)} nodes and {len(graph.edges)} edges")
            
            # Get LLM engine used
            llm_used = self.extractor.llm_router.last_used_provider or "unknown"
            
            # Create response
            response = ProcessResponse(
                profile=profile,
                graph=graph,
                llm_engine_used=llm_used
            )
            
            return {
                "success": True,
                "domain": domain,
                "profile": profile.dict(),
                "graph": graph.dict(),
                "llm_engine_used": llm_used
            }
            
        except FileNotFoundError as e:
            logger.error(f"File not found for {domain}: {e}")
            return {
                "success": False,
                "domain": domain,
                "error": f"File not found: {e}",
                "profile": None,
                "graph": None
            }
        except Exception as e:
            logger.error(f"Error processing {domain}: {e}", exc_info=True)
            return {
                "success": False,
                "domain": domain,
                "error": str(e),
                "profile": None,
                "graph": None
            }
    
    def save_profile(self, domain: str, result: Dict[str, Any]) -> None:
        """Save extracted profile to JSON file.
        
        Args:
            domain: Company domain
            result: Processing result dict
        """
        if not result.get("success"):
            logger.warning(f"Skipping save for {domain} due to processing failure")
            return
        
        output_file = self.output_dir / f"{domain}.json"
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False, default=str)
            logger.info(f"Saved profile to {output_file}")
        except Exception as e:
            logger.error(f"Failed to save profile for {domain}: {e}")
    
    def process_all(self, max_domains: int = None) -> Dict[str, Any]:
        """Process all available company domains.
        
        Args:
            max_domains: Maximum number of domains to process (None = all)
            
        Returns:
            Summary dict with success/failure counts
        """
        domains = self.loader.list_companies()
        
        if max_domains:
            domains = domains[:max_domains]
        
        logger.info(f"Processing {len(domains)} domains: {domains}")
        
        results = {
            "total": len(domains),
            "successful": 0,
            "failed": 0,
            "domains": {}
        }
        
        for domain in domains:
            result = self.process_domain(domain)
            results["domains"][domain] = result
            
            if result["success"]:
                results["successful"] += 1
                self.save_profile(domain, result)
            else:
                results["failed"] += 1
        
        # Save summary
        summary_file = self.output_dir / "batch_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"Batch processing complete: {results['successful']}/{results['total']} successful")
        
        return results


def main():
    """Main entry point for batch extraction."""
    import sys
    
    # Check if specific domain provided
    if len(sys.argv) > 1:
        domain = sys.argv[1]
        extractor = BatchExtractor()
        result = extractor.process_domain(domain)
        extractor.save_profile(domain, result)
        print(f"\nProcessing complete for {domain}")
        print(f"Success: {result['success']}")
        if result.get('error'):
            print(f"Error: {result['error']}")
    else:
        # Process all domains
        extractor = BatchExtractor()
        results = extractor.process_all()
        
        print("\n" + "="*60)
        print("BATCH EXTRACTION SUMMARY")
        print("="*60)
        print(f"Total domains: {results['total']}")
        print(f"Successful: {results['successful']}")
        print(f"Failed: {results['failed']}")
        print(f"\nResults saved to: {extractor.output_dir}")
        print("="*60)


if __name__ == "__main__":
    main()

