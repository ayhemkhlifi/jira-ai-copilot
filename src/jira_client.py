"""
=============================================================================
Jira AI Copilot — Jira REST API Client (Write Operations)
=============================================================================

Creates issues in Jira Cloud and saves them to Qdrant for the learning loop.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from src.utils.console import console
from src.models.ticket import JiraTicket

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

def _env(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else default

JIRA_BASE_URL: str = _env("JIRA_BASE_URL")
JIRA_EMAIL: str = _env("JIRA_EMAIL")
JIRA_API_TOKEN: str = _env("JIRA_API_TOKEN")
JIRA_PROJECT_KEY: str = _env("JIRA_PROJECT_KEY")

# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------

class PushTicketRequest(BaseModel):
    """Request body for pushing approved tickets to Jira."""
    tickets: list[JiraTicket] = Field(..., description="List of approved tickets")

class TicketCreationResult(BaseModel):
    """Result for a single ticket creation attempt."""
    draft_id: str = ""
    title: str = ""
    status: str = "pending" # created | failed
    jira_key: Optional[str] = None
    jira_url: Optional[str] = None
    error: Optional[str] = None

class PushTicketsResponse(BaseModel):
    """Response body for push-tickets endpoint."""
    success: bool = True
    total: int = 0
    created: int = 0
    failed: int = 0
    results: list[TicketCreationResult] = Field(default_factory=list)

# -----------------------------------------------------------------------------
# Jira REST API — Issue Creation
# -----------------------------------------------------------------------------

def _get_jira_auth() -> tuple[str, str]:
    if not all([JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN]):
        raise ValueError("Missing Jira credentials in environment.")
    return JIRA_EMAIL, JIRA_API_TOKEN

def _build_description_adf(ticket: JiraTicket) -> dict:
    """Convert ticket info to Atlassian Document Format."""
    content = []
    
    if ticket.description:
        content.append({
            "type": "paragraph",
            "content": [{"type": "text", "text": ticket.description}]
        })

    if ticket.acceptance_criteria:
        content.append({"type": "heading", "attrs": {"level": 3}, "content": [{"type": "text", "text": "Acceptance Criteria"}]})
        items = [{"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": ac}]}]} for ac in ticket.acceptance_criteria]
        content.append({"type": "bulletList", "content": items})

    return {"version": 1, "type": "doc", "content": content}

def create_jira_issue(ticket: JiraTicket, project_key: str | None = None) -> Dict[str, Any]:
    project_key = project_key or JIRA_PROJECT_KEY
    auth = _get_jira_auth()
    base_url = JIRA_BASE_URL.rstrip("/")

    fields = {
        "project": {"key": project_key},
        "summary": ticket.title,
        "issuetype": {"name": ticket.type if ticket.type in ["Epic", "Story", "Task", "Bug"] else "Task"},
        "priority": {"name": ticket.priority if ticket.priority in ["Highest", "High", "Medium", "Low", "Lowest"] else "Medium"},
        "description": _build_description_adf(ticket),
    }

    if ticket.labels:
        fields["labels"] = ticket.labels

    url = f"{base_url}/rest/api/3/issue"
    response = requests.post(url, json={"fields": fields}, auth=auth, timeout=30)
    response.raise_for_status()

    data = response.json()
    return {
        "jira_key": data["key"],
        "jira_url": f"{base_url}/browse/{data['key']}",
        "jira_id": data["id"]
    }

def push_tickets_to_jira(tickets: list[JiraTicket], save_to_qdrant: bool = True) -> PushTicketsResponse:
    results = []
    created_count = 0
    failed_count = 0

    for i, ticket in enumerate(tickets):
        draft_id = f"DRAFT-{i+1:03d}"
        try:
            res = create_jira_issue(ticket)
            results.append(TicketCreationResult(
                draft_id=draft_id,
                title=ticket.title,
                status="created",
                jira_key=res["jira_key"],
                jira_url=res["jira_url"]
            ))
            created_count += 1

            if save_to_qdrant:
                from src.jira_ingestion import ticket_to_document, ingest_jira_tickets
                # Synthetic issue for ingestion
                synthetic = {"key": res["jira_key"], "fields": {"summary": ticket.title, "description": ticket.description, "status": {"name": "To Do"}, "priority": {"name": ticket.priority}, "issuetype": {"name": ticket.type}}}
                ingest_jira_tickets([ticket_to_document(synthetic)])

        except Exception as e:
            results.append(TicketCreationResult(draft_id=draft_id, title=ticket.title, status="failed", error=str(e)))
            failed_count += 1

    return PushTicketsResponse(success=failed_count == 0, total=len(tickets), created=created_count, failed=failed_count, results=results)
