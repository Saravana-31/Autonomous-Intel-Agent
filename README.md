# Offline Company Intelligence Agent

An autonomous agent that extracts structured company intelligence from offline website snapshots using a **tiered extraction architecture** combining deterministic rules + LLM reasoning.

## ⚡ Architecture Overview (v2.0)

This system implements a **3-layer tiered extraction** to guarantee all mandatory fields are always returned:

### Layer 1: Deterministic Extraction (Fast, Rule-Based)
- **No LLM required** — uses regex, HTML parsing, and heuristics
- Extracts with high confidence:
  - Email addresses and phone numbers
  - Social media links (LinkedIn, Twitter, GitHub, etc.)
  - Physical addresses, cities, countries
  - Domain names and company metadata
  - Certifications (keyword-based)
  - People mentions (capitalized names)

### Layer 2: LLM Extraction (Primary: Ollama, Fallback: Phi-2)
- **Ollama (Online)** — Primary LLM provider
  - Uses OpenAI-compatible API
  - Configurable model (default: `llama3.1`)
  - Configurable endpoint (default: `http://localhost:11434`)
  - Runs locally or remotely
- **Phi-2 (Local)** — Offline fallback
  - Microsoft Phi-2 via Hugging Face Transformers
  - ~5GB model, CPU-only
  - Activates if Ollama is unreachable

### LLM Responsibilities
LLMs are used **only** for:
- Industry and sub-industry classification
- Company description synthesis
- Role normalization (standardize job titles)
- Service/product normalization (deduplicate, fix typos)
- Certification validation

### Why This Design?
✅ **Deterministic layer is fast** — No network latency for core fields  
✅ **LLM layer is flexible** — Online or offline, Ollama or Phi-2  
✅ **Fallback is automatic** — Silent, transparent layer switching  
✅ **Never crashes** — Returns "unknown" for missing data, not errors  
✅ **Offline-ready** — Phi-2 ensures extraction works without internet  
✅ **Scalable** — Swap Ollama model/endpoint via ENV vars  

## Features

- **Hybrid Extraction**: Deterministic + LLM for accuracy
- **Online-Primary**: Ollama (configurable endpoint/model)
- **Offline-Fallback**: Local Phi-2 (automatic, silent)
- **CPU-Only**: No GPU required
- **Structured Output**: Validated JSON with Pydantic
- **Mandatory Fields**: All schemas enforced strictly
- **Knowledge Graph**: Deterministically built from extracted data
- **React UI**: View results in real-time

## Project Structure

```
backend/
├── main.py              # FastAPI server
├── loader.py            # HTML file loader
├── cleaner.py           # HTML cleaning utilities
├── deterministic.py     # Layer 1: rule-based extraction
├── tiered_extractor.py  # Orchestration (deterministic + LLM)
├── schema.py            # Pydantic data models (mandatory fields)
├── graph_builder.py     # Knowledge graph builder
├── llm/
│   ├── __init__.py
│   ├── base.py          # BaseLLM abstract interface
│   ├── ollama_cloud.py  # Ollama provider (primary)
│   ├── phi2_local.py    # Phi-2 provider (fallback)
│   └── router.py        # LLMRouter with fallback logic
├── llm_engine.py        # Phi-2 (preserved for compat)
├── extractor.py         # Legacy extractor (for compat)
├── requirements.txt
└── data/
    └── example.com/
        ├── index.html
        └── about.html
```

## Setup Instructions

### Prerequisites

- Python 3.9+
- Node.js 16+
- 8GB+ RAM recommended
- ~5GB disk space (for Phi-2 fallback only)

### 1. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate
# Or (macOS/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Ollama (Optional but Recommended)

#### Option A: Use Local Ollama

**Install Ollama:**
- **macOS/Windows**: Download from https://ollama.ai
- **Linux**: `curl https://ollama.ai/install.sh | sh`

**Pull a model and start the server:**
```bash
ollama pull llama3.1
ollama serve
```

This starts Ollama at `http://localhost:11434` by default.

#### Option B: Use Remote Ollama

If you have an Ollama instance running on another machine:
```bash
export OLLAMA_BASE_URL=http://<remote-host>:11434
export OLLAMA_MODEL=llama3.1
python main.py
```

#### Option C: Run Without Ollama (Offline-Only)

The system will automatically detect Ollama is unavailable and use Phi-2:
```bash
python main.py
```
Phi-2 will be downloaded (~5GB) and cached on first run.

### 3. Configure LLM Provider (Environment Variables)

**Default configuration** (online-primary + offline-fallback):
```bash
# Use defaults: Ollama at localhost:11434, model llama3.1
python main.py
```

**Custom Ollama endpoint:**
```bash
export OLLAMA_BASE_URL=http://your-server:11434
export OLLAMA_MODEL=neural-chat        # or your preferred model
export OLLAMA_TIMEOUT=120              # Request timeout in seconds
python main.py
```

**Force offline-only (Phi-2):**
```bash
export USE_OLLAMA=false  # (not yet implemented, but can add)
python main.py
```

### 4. Frontend Setup

```bash
cd frontend/react-ui
npm install
npm start
```

The frontend opens at `http://localhost:3000`.
cd offline-company-intel/frontend/react-ui

# Install dependencies
npm install
```

## Running the Application

### Start Backend Server

**Step 1: Optional — Start Ollama (in a new terminal)**
```bash
ollama serve
```

**Step 2: Start FastAPI backend**
```bash
cd backend
python main.py
```

The backend will:
1. Check Ollama health (if available)
2. Start on `http://localhost:8000`
3. Print extraction mode (Ollama or Phi-2)
4. Display "Ready to process requests!" when ready

### Start Frontend

```bash
# From another terminal
cd frontend/react-ui
npm start
```

Frontend opens at `http://localhost:3000`

## Usage

1. Start Ollama (optional), backend, and frontend
2. **Check LLM status** at `GET /` or `GET /llm-health`
3. Select a company from dropdown
4. Click "Extract Intelligence"
5. View:
   - Extracted company profile (mandatory fields)
   - Knowledge graph
   - **llm_engine_used**: Shows which LLM was used ("Ollama" or "Phi-2")

## Mandatory Field Schemas

All extraction responses include these mandatory fields (with fallback to "unknown"):

### Company Information
```json
{
  "company_name": "string",
  "domain": "string",
  "description": "string",
  "industry": "string (LLM-classified)",
  "sub_industry": "string",
  "services_offered": ["string"],
  "products_offered": ["string"]
}
```

### Contact Information
```json
{
  "email_addresses": ["string"],
  "phone_numbers": ["string"],
  "physical_address": "string",
  "city": "string",
  "country": "string"
}
```

### Services & Products
```json
[
  {
    "domain": "string",
    "name": "string",
    "type": "service | product"
  }
]
```

### People Information
```json
[
  {
    "person_name": "string",
    "role": "string (LLM-normalized)",
    "associated_company": "string"
  }
]
```

### Social Media
```json
[
  {
    "platform": "string",
    "url": "string"
  }
]
```

## API Reference

### Health Check
```
GET /
```
Returns server status and LLM availability.

**Response:**
```json
{
  "status": "running",
  "version": "2.0.0",
  "extraction_mode": "tiered (deterministic + LLM)",
  "llm": {
    "primary": {"name": "Ollama", "available": true},
    "fallback": {"name": "Phi-2", "available": true},
    "last_used": "Ollama"
  }
}
```

### LLM Health
```
GET /llm-health
```
Detailed LLM provider health information.

### List Companies
```
GET /companies
```
Returns available company directories.

### Process Company
```
GET /process/{company}
```
Extracts intelligence from company's HTML files.

**Response:**
```json
{
  "profile": {
    "company_information": { ... },
    "contact_information": { ... },
    "services": [ ... ],
    "people": [ ... ],
    "social_media": [ ... ],
    "certifications": [ ... ]
  },
  "graph": {
    "nodes": [ ... ],
    "edges": [ ... ]
  },
  "llm_engine_used": "Ollama"
}
```

## Adding New Company Data

1. Create a new folder in `backend/data/` with the company domain name:
   ```
   backend/data/newcompany.com/
   ```

2. Add HTML files (website snapshots):
   ```
   backend/data/newcompany.com/
   ├── index.html
   ├── about.html
   └── contact.html
   ```

3. Restart backend or refresh frontend

## Troubleshooting

### Ollama health check fails
**Problem**: "Ollama unreachable — using Phi-2"

**Solutions**:
1. Verify Ollama is running:
   ```bash
   ollama serve
   ```
2. Check endpoint:
   ```bash
   curl http://localhost:11434/v1/models
   ```
3. Verify model is pulled:
   ```bash
   ollama list
   ollama pull llama3.1
   ```
4. Check custom endpoint:
   ```bash
   echo $OLLAMA_BASE_URL
   ```

### Phi-2 model loading fails
- Ensure 8GB+ RAM available
- Check disk space (~5GB needed)
- Try: `python -c "from transformers import AutoModelForCausalLM, AutoTokenizer; AutoTokenizer.from_pretrained('microsoft/phi-2', trust_remote_code=True); AutoModelForCausalLM.from_pretrained('microsoft/phi-2', trust_remote_code=True)"`

### Out of memory errors
- Close other applications
- Reduce `max_chars` in `cleaner.py`
- Reduce `max_new_tokens` in `tiered_extractor.py`

### Slow extraction
- Deterministic layer: < 1 second
- LLM layer (Ollama): 5-10 seconds (network-dependent)
- LLM layer (Phi-2): 30-60 seconds on CPU
- First Phi-2 run: +5-10 minutes for model download

### CORS errors in frontend
- Ensure backend is running on port 8000
- Check CORS middleware is enabled in `main.py`

## Performance Characteristics

### Deterministic Layer (Always Fast)
- **Time**: < 1 second
- **CPU**: Minimal
- **Memory**: Negligible

### Ollama (Online LLM)
- **Time**: 5-10 seconds (depends on network + model)
- **Model**: Configurable (default: llama3.1)
- **Endpoint**: Configurable (local or remote)
- **Requirements**: No local model download

### Phi-2 (Offline Fallback)
- **Time**: 30-60 seconds per extraction
- **Memory**: ~4-6GB RAM
- **Model Size**: ~5GB on disk
- **Requirements**: First run downloads model

## Design Philosophy

### Why Tiered?
- **Deterministic first** — Fast, reliable extraction for known patterns
- **LLM as refinement** — Normalization, classification, synthesis
- **Graceful fallback** — Always offline-capable

### Why Ollama Primary?
- **Faster than Phi-2** — 5-10s vs 30-60s
- **Flexible deployment** — Run locally or remotely
- **Model choice** — Swap models via ENV var
- **Better reasoning** — Larger models (llama3.1, mistral, etc.)

### Why Phi-2 Fallback?
- **Offline capability** — No internet required
- **Lightweight** — Runs on CPU
- **Deterministic** — Same model, same output
- **Reliable** — Never dependent on network

### Why Never Crash?
- All mandatory fields have "unknown" default
- Extraction errors trigger layer 2 (LLM)
- LLM errors fallback gracefully
- Final response always valid JSON

## Advanced Usage

### Use a Different Ollama Model

```bash
export OLLAMA_MODEL=mistral
python main.py
```

Available models: `ollama list` or see https://ollama.ai/library

### Use a Remote Ollama Server

```bash
export OLLAMA_BASE_URL=http://gpu-server.internal:11434
export OLLAMA_MODEL=llama3.1
python main.py
```

### Increase Ollama Timeout

```bash
export OLLAMA_TIMEOUT=180  # 3 minutes for large models
python main.py
```

### Run in Offline-Only Mode

```bash
# Disable Ollama health check by setting unreachable URL
export OLLAMA_BASE_URL=http://192.0.2.1:11434
python main.py
```
The system will detect unreachable Ollama and use Phi-2.

## License

MIT License - Use freely for any purpose.
