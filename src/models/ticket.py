"""
=============================================================================
Jira AI Copilot — Ticket Data Models
=============================================================================

Pydantic models for structured Jira ticket output.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

# =============================================================================
# 1. ENUMS
# =============================================================================

class TicketType(str, Enum):
    """Jira issue types."""
    EPIC = "Epic"
    STORY = "Story"
    TASK = "Task"
    BUG = "Bug"
    SUBTASK = "Sub-task"

class Priority(str, Enum):
    """Jira priority levels."""
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"

class Component(str, Enum):
    """Common software project components."""
    BACKEND = "Backend"
    FRONTEND = "Frontend"
    INFRASTRUCTURE = "Infrastructure"
    QA = "QA"
    DESIGN = "Design"
    DEVOPS = "DevOps"
    DATA = "Data"

# =============================================================================
# 2. JIRA TICKET MODEL
# =============================================================================

class JiraTicket(BaseModel):
    """
    Structured representation of a single Jira ticket.
    All fields are designed to map directly to Jira REST API fields.
    """
    title: str = Field(
        ...,
        description="Clear, concise, action-oriented ticket title",
    )
    type: str = Field(
        default="Story",
        description="Issue type: Epic, Story, Task, Bug, Sub-task",
    )
    description: str = Field(
        default="",
        description="Detailed functional description",
    )
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        description="Testable acceptance criteria (Given/When/Then)",
    )
    non_functional_requirements: list[str] = Field(
        default_factory=list,
        description="Non-functional requirements (performance, security, compliance, etc.)",
    )
    priority: str = Field(
        default="Medium",
        description="Priority level: Critical, High, Medium, Low",
    )
    priority_justification: str = Field(
        default="",
        description="Rationale for the assigned priority",
    )
    story_points: int = Field(
        default=3,
        description="Estimated effort in Fibonacci scale (1,2,3,5,8,13)",
    )
    labels: list[str] = Field(
        default_factory=list,
        description="Categorization labels/tags",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="Blocking or related ticket references",
    )
    component: str = Field(
        default="Backend",
        description="Project component: Backend, Frontend, QA, etc.",
    )
    subtasks: list[str] = Field(
        default_factory=list,
        description="Suggested sub-task breakdown if ticket is large",
    )
    risks: list[str] = Field(
        default_factory=list,
        description="Identified risks or ambiguities",
    )

    # --- Augmented Fields from Pipeline ---
    confidence: float = Field(default=1.0)
    forced_review: bool = Field(default=False)
    anomaly_flags: list[dict] = Field(default_factory=list)
    estimations: dict = Field(default_factory=dict)
    subtasks_detailed: list[dict] = Field(default_factory=list)
    test_cases: list[dict] = Field(default_factory=list)


# =============================================================================
# 3. GENERATION RESULT
# =============================================================================

class TicketGenerationResult(BaseModel):
    """
    Complete result from the ticket generation agent.
    Wraps the list of generated tickets with metadata.
    """
    tickets: list[JiraTicket] = Field(
        default_factory=list,
        description="Generated Jira tickets",
    )
    source_query: str = Field(
        default="",
        description="Original user request that triggered generation",
    )
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO timestamp of generation",
    )
    ticket_count: int = Field(
        default=0,
        description="Number of tickets generated",
    )
    context_docs_used: int = Field(
        default=0,
        description="Number of context documents retrieved",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if generation failed",
    )
