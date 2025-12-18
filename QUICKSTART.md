"""
QUICK START GUIDE - Tiered LLM Extraction
==========================================

## 1. INSTALL DEPENDENCIES

cd backend
pip install -r requirements.txt

(Should install: fastapi, uvicorn, transformers, torch, beautifulsoup4, lxml, pydantic, pandas, accelerate, requests)


## 2. OPTION A: RUN WITH OLLAMA (Recommended)

Terminal 1 - Start Ollama:
  ollama pull llama3.1
  ollama serve

Terminal 2 - Start Backend:
  cd backend
  python main.py

Expected output:
  Starting Company Intelligence Agent...
  Initializing LLM router...
  Primary LLM: Ollama - Available: True
  Fallback LLM: Phi-2 - Available: False
  Ready to process requests!

Terminal 3 - Start Frontend:
  cd frontend/react-ui
  npm start

✓ Open http://localhost:3000
✓ Backend at http://localhost:8000
✓ Check status: curl http://localhost:8000/


## 2. OPTION B: RUN OFFLINE (Phi-2 Only)

Terminal 1 - Start Backend:
  cd backend
  python main.py

Expected output:
  Starting Company Intelligence Agent...
  Initializing LLM router...
  Primary LLM: Ollama - Available: False
  Fallback LLM: Phi-2 - Available: False
  Ready to process requests!
  (Phi-2 loads lazily on first extraction request)

Terminal 2 - Start Frontend (another terminal):
  cd frontend/react-ui
  npm start

✓ First extraction: ~45-60 seconds (model download + inference)
✓ Subsequent extractions: ~30-60 seconds (model cached)


## 3. CONFIGURE OLLAMA (Optional)

Use custom model:
  export OLLAMA_MODEL=mistral
  python main.py

Use remote Ollama:
  export OLLAMA_BASE_URL=http://gpu-server:11434
  export OLLAMA_MODEL=llama3.1
  python main.py

Increase timeout for large models:
  export OLLAMA_TIMEOUT=180
  python main.py


## 4. TEST ENDPOINTS

Health check:
  curl http://localhost:8000/
  curl http://localhost:8000/llm-health

List companies:
  curl http://localhost:8000/companies

Process a company:
  curl http://localhost:8000/process/example.com

Expected response includes:
  {
    "profile": {
      "company_name": "...",
      "company_information": {...},
      "contact_information": {...},
      "services": [...],
      "people": [...],
      "social_media": [...],
      "certifications": [...]
    },
    "graph": {...},
    "llm_engine_used": "Ollama"  ← Shows which LLM was used
  }


## 5. TROUBLESHOOTING

Ollama unreachable:
  ✓ Check: ollama serve is running
  ✓ Check: curl http://localhost:11434/v1/models
  ✓ System will automatically fall back to Phi-2

Phi-2 model download failing:
  ✓ Check disk space: 5GB+ free
  ✓ Check RAM: 8GB+ available
  ✓ Check internet: Model downloads from Hugging Face

Out of memory:
  ✓ Close other apps
  ✓ Reduce OLLAMA_TIMEOUT if network is slow
  ✓ Use smaller model: export OLLAMA_MODEL=neural-chat

Slow extraction (expected):
  ✓ Ollama: 5-10 seconds
  ✓ Phi-2: 30-60 seconds
  ✓ First Phi-2 run: +5-10 minutes for model download


## 6. ADD NEW COMPANY DATA

1. Create directory:
   mkdir backend/data/mycompany.com

2. Add HTML files:
   backend/data/mycompany.com/
   ├── index.html
   ├── about.html
   └── contact.html

3. Restart backend or refresh frontend
   API: curl http://localhost:8000/process/mycompany.com


## 7. KEY FILES & RESPONSIBILITIES

Core extraction:
  • tiered_extractor.py — Orchestrates deterministic + LLM
  • deterministic.py — Fast rule-based extraction
  • llm/router.py — Ollama → Phi-2 fallback logic

LLM providers:
  • llm/base.py — Abstract interface
  • llm/ollama_cloud.py — Ollama provider
  • llm/phi2_local.py — Phi-2 provider

Data models:
  • schema.py — Mandatory field schemas
  • graph_builder.py — Knowledge graph generation

API:
  • main.py — FastAPI server


## 8. WHAT GETS EXTRACTED (Mandatory Fields)

Deterministic (always fast):
  ✓ Emails, phones, social links
  ✓ Address, city, country
  ✓ Domain, company name from metadata
  ✓ Certifications (keyword match)
  ✓ People names

LLM-normalized (after deterministic):
  ✓ Industry classification
  ✓ Company description
  ✓ Service/product names (deduplicated)
  ✓ Job title normalization
  ✓ Certification validation


## 9. LOGS TO EXPECT

Healthy run (Ollama available):
  Starting Company Intelligence Agent...
  Initializing LLM router...
  Primary LLM: Ollama - Available: True
  Fallback LLM: Phi-2 - Available: False
  Ready to process requests!

  [During extraction]
  Layer 1: Running deterministic extraction...
  Deterministic extraction completed in 0.12s
  Layer 2: Running LLM extraction...
  Using Ollama for extraction
  Ollama extraction successful
  LLM extraction completed in 7.34s using Ollama
  Total extraction completed in 7.47s
  Built graph with 42 nodes and 58 edges

Fallback to Phi-2 (Ollama unavailable):
  Primary LLM: Ollama - Available: False
  Fallback LLM: Phi-2 - Available: False
  Ready to process requests!

  [During extraction]
  Layer 1: Running deterministic extraction...
  Deterministic extraction completed in 0.15s
  Layer 2: Running LLM extraction...
  Using Phi-2 for extraction
  Phi-2 extraction successful
  LLM extraction completed in 42.18s using Phi-2
  Total extraction completed in 42.33s
  Built graph with 38 nodes and 51 edges


## 10. SUCCESS INDICATORS

✓ GET / returns version 2.0.0 and LLM health info
✓ GET /llm-health shows at least one provider available
✓ GET /process/example.com returns llm_engine_used field
✓ Profile has company_information, contact_information, services, people, social_media fields
✓ All mandatory fields present (none are null)
✓ Extraction completes without errors

Go online: ollama serve + use Ollama (~10 seconds total)
Go offline: stop Ollama, system falls back to Phi-2 (~45 seconds total)
Both work seamlessly!
"""
