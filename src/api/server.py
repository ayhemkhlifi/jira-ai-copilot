"""
=============================================================================
Jira AI Copilot — FastAPI Server
=============================================================================

REST API for the Jira AI Copilot ticket generation agent.

Endpoints:
    POST /api/generate-tickets  — Generate Jira tickets from a request
    POST /api/push-tickets      — Push approved tickets to Jira + Qdrant
    GET  /api/health            — Health check
    GET  /atlassian-connect.json — Jira Connect App descriptor
    GET  /docs                  — Swagger UI (auto-generated)

Usage:
    python -m src.api.server
    # or
    uvicorn src.api.server:app --reload --port 8000
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

# Initialize console encoding first!
from src.utils.console import console

# (Imports moved to endpoints for lazy loading)
from src.jira_client import (
    PushTicketRequest,
    PushTicketsResponse,
    push_tickets_to_jira,
)

# =============================================================================
# 1. CONFIGURATION
# =============================================================================

# Calculate project root (assuming we are in src/api/server.py)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

# Frontend dist directory (built by Vite)
_FRONTEND_DIST = _PROJECT_ROOT / "frontend" / "dist"

# Base URL for the app (used in Connect descriptor)
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000")

# =============================================================================
# 2. API MODELS
# =============================================================================

class GenerateTicketsRequest(BaseModel):
    """Request body for ticket generation."""
    request: str = Field(
        ...,
        description="Natural language description of what tickets to generate",
        min_length=5,
        examples=[
            "Generate tickets from the payment feature meeting notes",
            "Analyze the backlog and suggest missing tickets",
        ],
    )

class GenerateTicketsResponse(BaseModel):
    """Response body containing generated tickets."""
    success: bool = Field(default=True)
    tickets: list[JiraTicket] = Field(default_factory=list)
    ticket_count: int = Field(default=0)
    source_query: str = Field(default="")
    generated_at: str = Field(default="")
    context_docs_used: int = Field(default=0)
    error: Optional[str] = Field(default=None)

class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(default="healthy")
    qdrant_connected: bool = Field(default=False)
    collection_exists: bool = False
    documents_count: int = 0
    llm_provider: str = ""
    timestamp: str = ""

# =============================================================================
# 3. FASTAPI APP
# =============================================================================

app = FastAPI(
    title="Jira AI Copilot API",
    description=(
        "AI-powered assistant for Agile delivery optimization. "
        "Generates structured Jira tickets from meeting notes, "
        "specifications, and backlog analysis using RAG + LangGraph."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    # Force allow Atlassian framing
    response.headers["Content-Security-Policy"] = "frame-ancestors 'self' https://*.atlassian.net https://*.atlassian.com https://*.jira.com"
    # Brute force remove any framing restrictions
    response.headers.pop("X-Frame-Options", None)
    response.headers.pop("x-frame-options", None)
    return response

# =============================================================================
# 4. API ENDPOINTS
# =============================================================================

@app.post(
    "/api/generate-tickets",
    response_model=GenerateTicketsResponse,
    summary="Generate Jira tickets",
)
async def generate_tickets(body: GenerateTicketsRequest) -> GenerateTicketsResponse:
    try:
        from src.agent.graph import run_agent
        from src.models.ticket import TicketGenerationResult
        
        result: TicketGenerationResult = run_agent(body.request)

        return GenerateTicketsResponse(
            success=result.error is None and result.ticket_count > 0,
            tickets=result.tickets,
            ticket_count=result.ticket_count,
            source_query=result.source_query,
            generated_at=result.generated_at,
            context_docs_used=result.context_docs_used,
            error=result.error,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ticket generation failed: {str(e)}",
        )


@app.post(
    "/api/push-tickets",
    response_model=PushTicketsResponse,
    summary="Push approved tickets to Jira",
)
async def push_tickets(body: PushTicketRequest) -> PushTicketsResponse:
    if not body.tickets:
        raise HTTPException(status_code=400, detail="No tickets provided.")

    try:
        result = push_tickets_to_jira(
            tickets=body.tickets,
            save_to_qdrant=True,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/health",
    response_model=HealthResponse,
    summary="Health check",
)
async def health_check() -> HealthResponse:
    from qdrant_client import QdrantClient

    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key = os.getenv("QDRANT_API_KEY", "")
    collection_name = os.getenv("QDRANT_COLLECTION", "jira_copilot_nomic")
    llm_provider = os.getenv("LLM_PROVIDER", "mistral")
    llm_model = os.getenv("LLM_MODEL", "mistral-medium")

    qdrant_connected = False
    collection_exists = False
    documents_count = 0

    try:
        # Crucial for Railway healthcheck: Use API Key for Qdrant Cloud
        client_kwargs = {"url": qdrant_url, "timeout": 5}
        if qdrant_api_key:
            client_kwargs["api_key"] = qdrant_api_key
        
        client = QdrantClient(**client_kwargs)
        collections = [c.name for c in client.get_collections().collections]
        qdrant_connected = True
        collection_exists = collection_name in collections

        if collection_exists:
            info = client.get_collection(collection_name)
            documents_count = info.points_count or 0
    except Exception as e:
        console.print(f"[red]Healthcheck Qdrant error: {e}[/red]")

    return HealthResponse(
        status="healthy" if qdrant_connected and collection_exists else "degraded",
        qdrant_connected=qdrant_connected,
        collection_exists=collection_exists,
        documents_count=documents_count,
        llm_provider=f"{llm_provider}/{llm_model}",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/atlassian-connect.json")
async def get_atlassian_connect_descriptor():
    """Serves the Atlassian Connect descriptor for Jira integration."""
    base_url = APP_BASE_URL.rstrip("/")

    return {
        "key": "com.jiracopilot.ai",
        "name": "Jira AI Copilot",
        "description": "AI Copilot that turns meeting notes into precise Jira tickets.",
        "vendor": {
            "name": "Jira AI Copilot Team",
            "url": base_url,
        },
        "baseUrl": base_url,
        "authentication": {
            "type": "none"
        },
        "apiVersion": 1,
        "modules": {
            "jiraProjectPages": [
                {
                    "url": "/",
                    "weight": 100,
                    "name": {
                        "value": "AI Copilot"
                    },
                    "key": "ai-copilot-project-page"
                }
            ]
        },
        "scopes": ["read", "write"]
    }


# =============================================================================
# 5. STATIC FILE SERVING (Frontend)
# =============================================================================

if _FRONTEND_DIST.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=str(_FRONTEND_DIST / "assets")),
        name="static-assets",
    )

    @app.get("/{full_path:path}")
    async def serve_frontend(request: Request, full_path: str):
        file_path = _FRONTEND_DIST / full_path
        if full_path and file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(_FRONTEND_DIST / "index.html"))


# =============================================================================
# 6. MAIN
# =============================================================================

def main():
    import uvicorn

    # Railway uses PORT environment variable
    port = int(os.getenv("PORT", os.getenv("API_PORT", "8000")))
    reload_enabled = os.getenv("API_RELOAD", "false").strip().lower() in {"1", "true", "yes"}
    
    console.print(f"\n[green]Starting Jira AI Copilot API on port {port}[/green]")
    
    uvicorn.run(
        "src.api.server:app",
        host="0.0.0.0",
        port=port,
        reload=reload_enabled,
    )

if __name__ == "__main__":
    main()
