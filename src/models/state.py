"""
=============================================================================
Jira AI Copilot — LangGraph State
=============================================================================

Defines the WorkspaceState used by the LangGraph agent.
"""

from __future__ import annotations

from typing import Any, Optional
from typing_extensions import TypedDict
from langchain_core.documents import Document

from src.models.ticket import JiraTicket, TicketGenerationResult

class WorkspaceState(TypedDict, total=False):
    """
    LangGraph state dictionary that flows through the agent nodes.
    """
    # --- Inputs & Control ---
    user_request: str
    input_chunks: list[str]
    task_type: str  # generation, analysis, estimation, etc.
    retry_count: int
    grader_errors: list[str]

    # --- Agent Outputs ---
    draft_tickets: list[dict]      # Ticket Generator output
    anomaly_flags: list[dict]      # Anomaly Detector output
    estimations: list[dict]        # Effort Estimator output
    subtasks: list[list[dict]]     # Subtasks Proposer output
    test_cases: list[list[dict]]    # Test Case Generator output

    # --- Working Context (Internal) ---
    retrieved_docs: list[Document]
    context: str
    raw_llm_output: str
    tickets: list[JiraTicket]
    result: TicketGenerationResult
    
    # --- Validation ---
    confidence_min: float
    forced_review: bool

    # --- Error handling ---
    error: Optional[str]

    # --- Metadata ---
    metadata: dict[str, Any]
