"""FastAPI backend for Company Intelligence Agent."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from schema import ProcessResponse, CompanyProfile, KnowledgeGraph
from loader import HTMLLoader
from cleaner import HTMLCleaner
from extractor import CompanyExtractor
from graph_builder import GraphBuilder
from llm_engine import get_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load LLM on startup."""
    print("Starting Company Intelligence Agent...")
    print("Loading LLM model (this may take a few minutes)...")
    engine = get_engine()
    engine.load_model()
    print("Ready to process requests!")
    yield
    print("Shutting down...")


app = FastAPI(
    title="Company Intelligence Agent",
    description="Offline autonomous agent for extracting company intelligence",
    version="1.0.0",
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
extractor = CompanyExtractor()
graph_builder = GraphBuilder()


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "running",
        "service": "Company Intelligence Agent",
        "llm_loaded": get_engine().is_loaded()
    }


@app.get("/companies")
async def list_companies():
    """List available company data directories."""
    companies = loader.list_companies()
    return {"companies": companies}


@app.get("/process/{company}", response_model=ProcessResponse)
async def process_company(company: str):
    """
    Process a company's website snapshot and extract intelligence.
    
    Args:
        company: Company domain name (directory name in /data/)
        
    Returns:
        ProcessResponse with profile and knowledge graph
    """
    # Check if company exists
    if not loader.company_exists(company):
        raise HTTPException(
            status_code=404,
            detail=f"Company '{company}' not found. Available: {loader.list_companies()}"
        )
    
    try:
        # Load HTML files
        html_files = loader.load_html_files(company)
        print(f"Loaded {len(html_files)} HTML files for {company}")
        
        # Clean and concatenate text
        cleaned_text = cleaner.process_files(html_files)
        truncated_text = cleaner.truncate_text(cleaned_text, max_chars=2500)
        print(f"Cleaned text length: {len(truncated_text)} chars")
        
        # Extract company profile
        print("Extracting company intelligence...")
        profile = extractor.extract(truncated_text)
        print(f"Extracted profile for: {profile.company_name}")
        
        # Build knowledge graph
        graph = graph_builder.build(profile)
        print(f"Built graph with {len(graph.nodes)} nodes and {len(graph.edges)} edges")
        
        return ProcessResponse(profile=profile, graph=graph)
        
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
