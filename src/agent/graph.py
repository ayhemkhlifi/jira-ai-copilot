"""
=============================================================================
Jira AI Copilot — LangGraph Execution
=============================================================================

Assembles the LangGraph and provides a high-level run function.
"""

from __future__ import annotations

from langgraph.graph import StateGraph, START, END
from rich.panel import Panel
from rich.table import Table

from src.utils.console import console
from src.models.state import WorkspaceState
from src.models.ticket import TicketGenerationResult
from src.agent.nodes import (
    supervisor_agent,
    router_node,
    retrieve_context, 
    generate_tickets, 
    parse_tickets,
    anomaly_detector_agent,
    effort_estimator_node,
    subtasks_proposer_node,
    test_case_generator_node,
    grader_node
)

def build_graph() -> StateGraph:
    """
    Build and compile the LangGraph ticket generation pipeline.
    """
    graph = StateGraph(WorkspaceState)

    # Add nodes
    graph.add_node("supervisor", supervisor_agent)
    graph.add_node("retrieve_context", retrieve_context)
    graph.add_node("generate_tickets", generate_tickets)
    graph.add_node("parse_tickets", parse_tickets)
    graph.add_node("anomaly_detector", anomaly_detector_agent)
    graph.add_node("effort_estimator", effort_estimator_node)
    graph.add_node("subtasks_proposer", subtasks_proposer_node)
    graph.add_node("test_case_generator", test_case_generator_node)
    graph.add_node("grader", grader_node)

    # Define edges based on the workflow diagram
    graph.add_edge(START, "supervisor")
    
    # Conditional edge from Supervisor/Router
    graph.add_conditional_edges(
        "supervisor",
        router_node,
        {
            "retrieve_context": "retrieve_context",
            "end": END
        }
    )

    graph.add_edge("retrieve_context", "generate_tickets")
    graph.add_edge("generate_tickets", "parse_tickets")
    
    # Pipeline wiring
    graph.add_edge("parse_tickets", "anomaly_detector")
    graph.add_edge("anomaly_detector", "effort_estimator")
    
    # Parallel nodes
    graph.add_edge("effort_estimator", "subtasks_proposer")
    graph.add_edge("effort_estimator", "test_case_generator")

    # Feed parallel into grader
    graph.add_edge("subtasks_proposer", "grader")
    graph.add_edge("test_case_generator", "grader")
    
    graph.add_edge("grader", END)

    compiled = graph.compile()
    console.print("[green]LangGraph agent compiled with Supervisor and Router[/green]")
    return compiled

def run_agent(user_request: str) -> TicketGenerationResult:
    """
    High-level function to run the full ticket generation pipeline.
    """
    console.print(
        Panel(
            f"[bold cyan]Running Ticket Generation Agent[/bold cyan]\n"
            f"Request: {user_request[:80]}...",
            title="LangGraph Agent",
            border_style="cyan",
        )
    )

    graph = build_graph()

    initial_state: WorkspaceState = {
        "user_request": user_request,
        "retrieved_docs": [],
        "context": "",
        "raw_llm_output": "",
        "tickets": [],
        "error": None,
        "metadata": {},
    }

    final_state = graph.invoke(initial_state)

    if final_state.get("error") or not final_state.get("tickets"):
        result = TicketGenerationResult(
            tickets=[],
            source_query=user_request,
            error=final_state.get("error", "Agent did not produce a result"),
        )
    else:
        tickets = final_state.get("tickets", [])
        # Merge augmented logic from other agents into the main ticket instances
        anomaly_flags = final_state.get("anomaly_flags", [])
        estimations = final_state.get("estimations", [])
        detailed_subtasks = final_state.get("subtasks", [])
        test_cases = final_state.get("test_cases", [])
        
        for i, ticket in enumerate(tickets):
            if i < len(anomaly_flags):
                ticket.anomaly_flags = [anomaly_flags[i]] if anomaly_flags[i].get("isDuplicate") or anomaly_flags[i].get("conflicts") or anomaly_flags[i].get("dependencies") else []
            if i < len(estimations):
                ticket.estimations = estimations[i]
                ticket.story_points = estimations[i].get("pertEstimate", ticket.story_points)
                ticket.confidence = estimations[i].get("confidence", 1.0) * 100
                ticket.forced_review = estimations[i].get("confidence", 1.0) < 0.5
            if i < len(detailed_subtasks):
                ticket.subtasks_detailed = detailed_subtasks[i]
            if i < len(test_cases):
                ticket.test_cases = test_cases[i]

        result = TicketGenerationResult(
            tickets=tickets,
            source_query=user_request,
            ticket_count=len(tickets),
            context_docs_used=final_state.get("metadata", {}).get("docs_retrieved", 0),
        )

    return result

def display_tickets(result: TicketGenerationResult) -> None:
    """Pretty-print the generated tickets using Rich."""
    if result.error and not result.tickets:
        console.print(f"[red]Error: {result.error}[/red]")
        return

    console.print(
        Panel(
            f"[bold green]Generated {result.ticket_count} tickets[/bold green]\n"
            f"Query: {result.source_query[:80]}\n"
            f"Context docs: {result.context_docs_used}\n"
            f"Generated at: {result.generated_at}",
            title="Generation Result",
            border_style="green",
        )
    )

    table = Table(title="Ticket Summary", show_lines=True, border_style="cyan")
    table.add_column("#", style="dim", width=3)
    table.add_column("Type", width=8)
    table.add_column("Priority", width=8)
    table.add_column("SP", width=4)
    table.add_column("Component", width=12)
    table.add_column("Title", width=55)

    for i, ticket in enumerate(result.tickets, 1):
        table.add_row(
            str(i),
            ticket.type,
            ticket.priority,
            str(ticket.story_points),
            ticket.component,
            ticket.title[:55],
        )

    console.print(table)

    for i, ticket in enumerate(result.tickets, 1):
        details = (
            f"[bold]{ticket.title}[/bold]\n\n"
            f"Type: {ticket.type} | Priority: {ticket.priority} | "
            f"SP: {ticket.story_points} | Component: {ticket.component}\n\n"
            f"Description:\n{ticket.description}\n\n"
            f"Acceptance Criteria:\n"
        )
        for ac in ticket.acceptance_criteria:
            details += f"  - {ac}\n"

        if ticket.labels:
            details += f"\nLabels: {', '.join(ticket.labels)}"
        if ticket.dependencies:
            details += f"\nDependencies: {', '.join(ticket.dependencies)}"
        if ticket.subtasks:
            details += "\nSub-tasks:\n"
            for st in ticket.subtasks:
                details += f"  - {st}\n"
        if ticket.risks:
            details += "\nRisks:\n"
            for r in ticket.risks:
                details += f"  - {r}\n"

        console.print(
            Panel(details, title=f"Ticket {i}: {ticket.type}", border_style="blue")
        )
