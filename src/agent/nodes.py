"""
=============================================================================
Jira AI Copilot — LangGraph Nodes
=============================================================================

Refactored Nodes: Now acts as a thin orchestration layer that calls 
modularized agents and logic.
"""

from __future__ import annotations
import json
import time

from src.utils.console import console
from src.models.ticket import JiraTicket, TicketGenerationResult
from src.models.state import WorkspaceState

# Import modular agents
from src.agent.agents.supervisor import SupervisorAgent
from src.agent.agents.ticket_generator import TicketGeneratorAgent
from src.agent.agents.anomaly_detector import anomaly_detector_agent, AnomalyDetectorAgent
from src.agent.agents.effort_estimator import effort_estimator_node
from src.agent.agents.subtasks_proposer import subtasks_proposer_node
from src.agent.agents.test_case_generator import test_case_generator_node
from src.agent.agents.grader import grader_node
from src.agent.logic import retrieve_context_logic

# Initialize Agent Instances
supervisor = SupervisorAgent()
ticket_gen = TicketGeneratorAgent()
anomaly_det = None


def _get_anomaly_detector() -> AnomalyDetectorAgent:
    """Lazily initialize anomaly detector to avoid blocking API startup."""
    global anomaly_det
    if anomaly_det is None:
        anomaly_det = AnomalyDetectorAgent()
    return anomaly_det

# =============================================================================
# 1. NODES (Thin Orchestrators)
# =============================================================================

def supervisor_agent(state: WorkspaceState) -> dict:
    """Matches the node name expected by graph.py"""
    return supervisor.run(state)

def router_node(state: WorkspaceState) -> str:
    """Read WorkspaceState and decide the sequence of agents to trigger based on current state."""
    console.print("[bold blue]>> Node: router_node[/bold blue]")
    
    if state.get("error"):
        return "end"
        
    # Check if we have any generated tickets in state (draft_tickets or tickets)
    has_tickets = bool(state.get("draft_tickets") or state.get("tickets") or state.get("raw_llm_output"))
    
    # State condition: draftTickets vide -> Route to Ticket Generator (via retrieval)
    if not has_tickets:
        console.print("   [dim]State: draft_tickets empty -> Routing to Ticket Generator pipeline[/dim]")
        return "retrieve_context"
    
    # Other state conditions (e.g., tickets exist but not checked for anomalies)
    if has_tickets and not state.get("anomaly_flags"):
        console.print("   [dim]State: tickets exist, no anomalies checked -> Routing to Anomaly Detector[/dim]")
        return "anomaly_detector"
    
    return "end"

def retrieve_context(state: WorkspaceState) -> dict:
    """Matches the node name expected by graph.py"""
    return retrieve_context_logic(state)

def generate_tickets(state: WorkspaceState) -> dict:
    """Matches the node name expected by graph.py"""
    if state.get("error"):
        return {}
    return ticket_gen.run(state)

def anomaly_detector_agent(state: WorkspaceState) -> dict:
    """Matches the node name expected by graph.py"""
    return _get_anomaly_detector().run(state)

def parse_tickets(state: WorkspaceState) -> dict:
    """Parses raw LLM JSON into objects."""
    console.print("[cyan]>> Node: parse_tickets[/cyan]")

    raw_output = state.get("raw_llm_output", "")
    user_request = state.get("user_request", "")
    metadata = state.get("metadata", {})

    if state.get("error") or not raw_output.strip():
        error_msg = state.get("error", "No LLM output to parse")
        return {
            "tickets": [],
            "error": error_msg
        }

    try:
        # Simple cleanup if LLM included backticks
        json_str = raw_output.strip()
        if json_str.startswith("```json"):
            json_str = json_str[7:-3].strip()
        elif json_str.startswith("```"):
            json_str = json_str[3:-3].strip()

        # strict=False allows unescaped control characters like newlines (\n) inside JSON strings
        data = json.loads(json_str, strict=False)
        tickets = [JiraTicket(**t) for t in data]

        console.print(f"   Successfully parsed [bold]{len(tickets)}[/bold] tickets")
        return {
            "tickets": tickets,
            "metadata": {**metadata, "ticket_count": len(tickets)}
        }
    except Exception as e:
        console.print(f"   [red]Parsing failed: {e}[/red]")
        return {"error": f"Parsing failed: {str(e)}"}
