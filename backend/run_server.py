#!/usr/bin/env python
"""Start the backend server in Windows-compatible mode."""

if __name__ == "__main__":
    import uvicorn
    import sys
    import os
    
    # Fix for Windows asyncio event loop
    if sys.platform == 'win32':
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Import app after setting event loop policy
    from main import app
    
    print("\n" + "="*60)
    print("Company Intelligence Agent - Backend Server")
    print("="*60)
    print("Ollama: Primary LLM (http://localhost:11434)")
    print("Phi-2:  Fallback LLM (local)")
    print("="*60 + "\n")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
