"""
=============================================================================
Jira AI Copilot — FastAPI Server
=============================================================================

REST API for the Jira AI Copilot ticket generation agent.

Endpoints:
    POST /api/generate-tickets  — Generate Jira tickets from a request
    GET  /api/health             — Health check
    GET  /docs                   — Swagger UI (auto-generated)

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
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Initialize console encoding first!
from src.utils.console import console

from src.agent.graph import run_agent
from src.models.ticket import JiraTicket, TicketGenerationResult

# =============================================================================
# 1. CONFIGURATION
# =============================================================================

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

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
    collection_exists: bool = Field(default=False)
    documents_count: int = Field(default=0)
    llm_provider: str = Field(default="")
    timestamp: str = Field(default="")

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# 4. ENDPOINTS
# =============================================================================

@app.post(
    "/api/generate-tickets",
    response_model=GenerateTicketsResponse,
    summary="Generate Jira tickets",
    description="Takes a natural language request and generates structured Jira tickets using RAG + LLM.",
)
async def generate_tickets(body: GenerateTicketsRequest) -> GenerateTicketsResponse:
    try:
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

@app.get(
    "/api/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Check the status of the API, Qdrant connection, and LLM provider.",
)
async def health_check() -> HealthResponse:
    from qdrant_client import QdrantClient

    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    collection_name = os.getenv("QDRANT_COLLECTION", "jira_copilot")
    llm_provider = os.getenv("LLM_PROVIDER", "mistral")
    llm_model = os.getenv("LLM_MODEL", "mistral-medium")

    qdrant_connected = False
    collection_exists = False
    documents_count = 0

    try:
        client = QdrantClient(url=qdrant_url, timeout=5)
        collections = [c.name for c in client.get_collections().collections]
        qdrant_connected = True
        collection_exists = collection_name in collections

        if collection_exists:
            info = client.get_collection(collection_name)
            documents_count = info.points_count or 0
    except Exception:
        pass

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
    # When deploying, this base_url should be your production HTTPS URL or Ngrok
    # Defaulting to a placeholder for local development
    base_url = "https://YOUR-NGROK-URL.ngrok-free.app"
    
    return {
        "key": "com.jiracopilot.ai",
        "name": "Jira AI Copilot",
        "description": "AI Copilot that turns meeting notes into precise Jira tickets.",
        "vendor": {
            "name": "Your Vendor Name",
            "url": "https://yourwebsite.com"
        },
        "baseUrl": base_url,
        "authentication": {
            "type": "none"  # Use "jwt" for production
        },
        "apiVersion": 1,
        "modules": {
            "jiraProjectPages": [
                {
                    "url": "/", # Assuming frontend is served from root or you map this
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
# 5. MAIN
# =============================================================================

def main():
    """Start the FastAPI server with uvicorn."""
    import uvicorn

    port = int(os.getenv("API_PORT", "8000"))
    reload_enabled = os.getenv("API_RELOAD", "false").strip().lower() in {"1", "true", "yes"}
    console.print(f"\n[green]Starting Jira AI Copilot API on http://localhost:{port}[/green]")
    console.print(f"[green]Swagger UI: http://localhost:{port}/docs[/green]\n")

    uvicorn.run(
        "src.api.server:app",
        host="0.0.0.0",
        port=port,
        reload=reload_enabled,
    )

if __name__ == "__main__":
    main()
