# Offline Company Intelligence Agent

An autonomous agent that extracts structured company intelligence from offline website snapshots using a local LLM (Microsoft Phi-2).

## Features

- **Fully Offline**: No cloud APIs required
- **Local LLM**: Uses Microsoft Phi-2 via Hugging Face Transformers
- **CPU-Only**: Runs on standard laptops without GPU
- **Structured Output**: Returns validated JSON with Pydantic
- **Knowledge Graph**: Builds nodes and edges for visualization
- **React UI**: Clean, minimal frontend for viewing results

## Project Structure

```
offline-company-intel/
├── backend/
│   ├── main.py           # FastAPI server
│   ├── loader.py         # HTML file loader
│   ├── cleaner.py        # HTML cleaning utilities
│   ├── llm_engine.py     # Phi-2 LLM interface
│   ├── extractor.py      # Company info extraction
│   ├── schema.py         # Pydantic data models
│   ├── graph_builder.py  # Knowledge graph builder
│   ├── requirements.txt  # Python dependencies
│   └── data/
│       └── example.com/  # Sample website snapshot
│           ├── index.html
│           └── about.html
└── frontend/
    └── react-ui/         # React frontend
        ├── package.json
        ├── public/
        └── src/
```

## Setup Instructions

### Prerequisites

- Python 3.9+ 
- Node.js 16+
- 8GB+ RAM recommended
- ~5GB disk space for model

### 1. Backend Setup

```bash
# Navigate to backend directory
cd offline-company-intel/backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Download the LLM Model (First Run)

The model (~5GB) will be downloaded automatically on first run. To pre-download:

```bash
# Activate virtual environment first, then:
python -c "from transformers import AutoModelForCausalLM, AutoTokenizer; AutoTokenizer.from_pretrained('microsoft/phi-2', trust_remote_code=True); AutoModelForCausalLM.from_pretrained('microsoft/phi-2', trust_remote_code=True)"
```

This will cache the model in `~/.cache/huggingface/`.

### 3. Frontend Setup

```bash
# Navigate to frontend directory
cd offline-company-intel/frontend/react-ui

# Install dependencies
npm install
```

## Running the Application

### Start Backend Server

```bash
# From backend directory with venv activated
cd offline-company-intel/backend
python main.py
```

The server will:
1. Load the Phi-2 model (may take 2-5 minutes on first run)
2. Start on http://localhost:8000
3. Display "Ready to process requests!" when ready

### Start Frontend

```bash
# From frontend directory (in a new terminal)
cd offline-company-intel/frontend/react-ui
npm start
```

The frontend will open at http://localhost:3000

## Usage

1. Start both backend and frontend servers
2. Wait for the "LLM Ready" status in the UI
3. Select a company from the dropdown (e.g., "example.com")
4. Click "Extract Intelligence"
5. View the extracted company profile and knowledge graph

## Adding New Company Data

1. Create a new folder in `backend/data/` with the company domain name:
   ```
   backend/data/newcompany.com/
   ```

2. Add HTML files (website snapshots) to the folder:
   ```
   backend/data/newcompany.com/
   ├── index.html
   ├── about.html
   └── contact.html
   ```

3. Restart the backend server or refresh the frontend

## API Reference

### Health Check
```
GET /
```
Returns server status and LLM load state.

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
    "company_name": "string",
    "description_short": "string",
    "industry": "string",
    "products_services": ["string"],
    "locations": ["string"],
    "key_people": [{"name": "", "title": "", "role_category": ""}],
    "contact": {"email": "", "phone": ""},
    "tech_stack": ["string"]
  },
  "graph": {
    "nodes": [{"id": "", "type": "", "label": "", "properties": {}}],
    "edges": [{"source": "", "target": "", "relationship": ""}]
  }
}
```

## Troubleshooting

### Model loading fails
- Ensure 8GB+ RAM available
- Check disk space (~5GB needed)
- Try setting `PYTORCH_ENABLE_MPS_FALLBACK=1` on macOS

### Out of memory errors
- Close other applications
- Reduce `max_chars` in `cleaner.py`
- Reduce `max_new_tokens` in `llm_engine.py`

### Slow generation
- Expected on CPU: 30-60 seconds per extraction
- First run downloads model (~5GB)
- Subsequent runs use cached model

### CORS errors in frontend
- Ensure backend is running on port 8000
- Check that CORS middleware is enabled

## Performance Notes

- **Memory**: ~4-6GB RAM during inference
- **Extraction Time**: 30-60 seconds on modern CPU
- **Model Size**: ~5GB on disk
- **Supported Text**: Up to ~2500 chars per extraction

## License

MIT License - Use freely for any purpose.
