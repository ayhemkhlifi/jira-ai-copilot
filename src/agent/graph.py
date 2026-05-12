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

    try:
        final_state = graph.invoke(initial_state)

        if not final_state or not final_state.get("tickets"):
            return TicketGenerationResult(
                tickets=[],
                source_query=user_request,
                error=final_state.get("error") if final_state else "Agent produced no tickets"
            )

        tickets = final_state.get("tickets", [])
        
        # Build maps for safe merging
        anomaly_map = {f.get("ticketRef"): f for f in final_state.get("anomaly_flags", []) if isinstance(f, dict)}
        est_map = {e.get("ticketRef"): e for e in final_state.get("estimations", []) if isinstance(e, dict)}
        
        subtask_list = final_state.get("subtasks", [])
        test_case_list = final_state.get("test_cases", [])
        
        for i, ticket in enumerate(tickets):
            try:
                # 1. Merge Anomaly Flags
                flag = anomaly_map.get(ticket.title)
                if flag:
                    ticket.anomaly_flags = [flag]
                    if "dependencies" in flag:
                        ticket.dependencies = list(set(ticket.dependencies + flag["dependencies"]))
                
                # 2. Merge Estimations
                est = est_map.get(ticket.title)
                if est:
                    ticket.estimations = est
                    ticket.story_points = est.get("pertEstimate", ticket.story_points)
                    ticket.confidence = est.get("confidence", 1.0) * 100
                
                # 3. Merge Subtasks & Test Cases
                if i < len(subtask_list):
                    ticket.subtasks_detailed = subtask_list[i]
                if i < len(test_case_list):
                    ticket.test_cases = test_case_list[i]
            except Exception as inner_e:
                console.print(f"[yellow]Warning: Failed to merge data for ticket '{ticket.title}': {inner_e}[/yellow]")

        return TicketGenerationResult(
            tickets=tickets,
            source_query=user_request,
            ticket_count=len(tickets),
            context_docs_used=final_state.get("metadata", {}).get("docs_retrieved", 0),
        )

    except Exception as e:
        import traceback
        console.print(f"[bold red]Pipeline Crash:[/bold red] {str(e)}")
        console.print(traceback.format_exc()) # This will show us the EXACT line that failed
        return TicketGenerationResult(
            tickets=[],
            source_query=user_request,
            error=f"Pipeline execution failed: {str(e)}"
        )

        return TicketGenerationResult(
            tickets=tickets,
            source_query=user_request,
            ticket_count=len(tickets),
            context_docs_used=final_state.get("metadata", {}).get("docs_retrieved", 0),
        )

    except Exception as e:
        console.print(f"[bold red]Pipeline Crash: {e}[/bold red]")
        return TicketGenerationResult(
            tickets=[],
            source_query=user_request,
            error=f"Pipeline execution failed: {str(e)}"
        )

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
