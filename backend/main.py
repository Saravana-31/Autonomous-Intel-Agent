"""FastAPI backend for Company Intelligence Agent.

Implements tiered extraction:
1. Deterministic layer (fast, rule-based)
2. LLM layer (Ollama primary, Phi-2 fallback)
"""

import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from schema import ProcessResponse, CompanyProfile, KnowledgeGraph
from loader import HTMLLoader
from cleaner import HTMLCleaner
from tiered_extractor import TieredExtractor
from graph_builder import GraphBuilder
from llm.router import LLMRouter
from cache_manager import CacheManager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize on startup (health checks only, no model loading)."""
    print("Starting Company Intelligence Agent...")
    print("Initializing LLM router...")
    
    llm_router = LLMRouter()
    health = llm_router.health_check()
    
    print(f"Primary LLM: {health['primary']['name']} - Available: {health['primary']['available']}")
    print(f"Fallback LLM: {health['fallback']['name']} - Available: {health['fallback']['available']}")
    
    if not (health['primary']['available'] or health['fallback']['available']):
        print("WARNING: No LLM providers available!")
    
    print("Ready to process requests!")
    yield
    print("Shutting down...")


app = FastAPI(
    title="Company Intelligence Agent",
    description="Tiered extraction: deterministic + LLM (Ollama/Phi-2) with offline fallback",
    version="2.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
loader = HTMLLoader()
cleaner = HTMLCleaner()
tiered_extractor = TieredExtractor()
graph_builder = GraphBuilder()
llm_router = LLMRouter()
cache_manager = CacheManager()


@app.get("/")
async def root():
    """Health check endpoint."""
    health = llm_router.health_check()
    return {
        "status": "running",
        "service": "Company Intelligence Agent",
        "version": "2.0.0",
        "extraction_mode": "tiered (deterministic + LLM)",
        "llm": health
    }


@app.get("/companies")
async def list_companies():
    """List available company data directories."""
    companies = loader.list_companies()
    return {"companies": companies}


@app.get("/llm-health")
async def llm_health():
    """Return LLM provider health information."""
    try:
        health = llm_router.health_check()
        return health
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {e}")


@app.get("/process/{company}", response_model=ProcessResponse)
async def process_company(company: str):
    """
    Process a company's website snapshot using tiered extraction.
    
    Combines:
    1. Deterministic extraction (fast, rule-based)
    2. LLM extraction (Ollama → Phi-2 fallback)
    
    Args:
        company: Company domain name (directory name in /data/)
        
    Returns:
        ProcessResponse with profile, graph, and llm_engine_used
    """
    # Check if company exists
    if not loader.company_exists(company):
        raise HTTPException(
            status_code=404,
            detail=f"Company '{company}' not found. Available: {loader.list_companies()}"
        )
    
    try:
        # Check cache first
        cached_data = cache_manager.load_cache(company)
        if cached_data:
            logger.info(f"Loading cached profile for {company} (skipping extraction)")
            profile = CompanyProfile(**cached_data['profile'])
            graph = KnowledgeGraph(**cached_data['graph'])
            llm_used = cached_data.get('metadata', {}).get('extraction_mode', 'cached')
            
            return ProcessResponse(
                profile=profile,
                graph=graph,
                llm_engine_used=llm_used
            )
        
        # Cache miss - run extraction
        # Load HTML files
        html_files = loader.load_html_files(company)
        logger.info(f"Loaded {len(html_files)} HTML files for {company}")
        
        # Clean and concatenate text
        cleaned_text = cleaner.process_files(html_files)
        truncated_text = cleaner.truncate_text(cleaned_text, max_chars=2500)
        logger.info(f"Cleaned text length: {len(truncated_text)} chars")
        
        # Extract company profile using tiered approach (with timeout control)
        import time
        extraction_start = time.time()
        
        logger.info("Starting tiered extraction...")
        try:
            profile = tiered_extractor.extract(truncated_text, company_domain=company, html_files=html_files, use_cache=False)
            logger.info(f"Extracted profile for: {profile.company_name}")
        except (ValueError, RuntimeError) as e:
            # JSON validation failed - don't cache, but try to return deterministic profile
            logger.error(f"Extraction failed due to invalid JSON: {e}")
            # Re-raise to prevent caching
            raise HTTPException(status_code=500, detail=f"Extraction failed: Invalid JSON from LLM")
        
        extraction_duration = time.time() - extraction_start
        if extraction_duration > 25:
            logger.warning(f"Extraction took {extraction_duration:.2f}s (exceeded 25s limit)")
        
        # Check if JSON validation failed (don't cache)
        json_validation_failed = getattr(profile, '_llm_json_failed', False)
        extraction_status = "repaired" if json_validation_failed else "complete"
        
        # Build knowledge graph
        graph = graph_builder.build(profile)
        logger.info(f"Built graph with {len(graph.nodes)} nodes and {len(graph.edges)} edges")
        
        # Get LLM engine used
        llm_used = tiered_extractor.llm_router.last_used_provider or "unknown"
        model_name = "llama3.1" if llm_used.lower() == "ollama" else "phi-2"
        
        # Determine extraction confidence
        extraction_confidence = "high"
        if llm_used == "unknown":
            extraction_confidence = "low"
        elif profile.people_status == "validated_absent" and len(profile.people_information) == 0:
            # Medium confidence if no people found (might be extraction issue)
            extraction_confidence = "medium"
        
        # Save to cache (ONLY AFTER schema validation)
        try:
            # Validate profile before caching
            from post_extraction_validator import validate_profile
            validate_profile(profile)
            # Cache repaired JSON if parsing succeeded
            cache_manager.save_cache(company, profile, graph, llm_used, model_name, extraction_confidence, extraction_status)
            logger.info(f"Cached profile for {company} (status: {extraction_status})")
        except Exception as e:
            logger.warning(f"Failed to cache profile for {company}: {e}")
            # Don't raise - return profile anyway, but don't cache invalid data
        
        return ProcessResponse(
            profile=profile,
            graph=graph,
            llm_engine_used=llm_used
        )
        
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Processing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    import sys
    
    # Fix for Windows asyncio event loop
    if sys.platform == 'win32':
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
