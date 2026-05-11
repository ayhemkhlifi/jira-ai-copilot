"""
=============================================================================
Jira AI Copilot — Agent Pipeline Test
=============================================================================

Standalone test script that runs the full LangGraph pipeline
and validates the output.

Usage:
    python -m tests.test_agent
"""

from __future__ import annotations

import json
from rich.panel import Panel

# Make sure console init is executed first
from src.utils.console import console

from src.agent.graph import run_agent, display_tickets
from src.models.ticket import TicketGenerationResult

def test_payment_feature():
    """Test ticket generation from payment feature meeting notes."""
    console.rule("[bold blue]Test 1: Payment Feature Tickets[/bold blue]")

    result = run_agent(
        "Generate Jira tickets from the meeting notes about the new "
        "payment feature. Include user stories, technical tasks, and "
        "security-related tickets."
    )

    _validate_result(result, "Payment Feature")
    display_tickets(result)
    return result

def test_backlog_analysis():
    """Test backlog analysis from existing Jira tickets."""
    console.rule("[bold blue]Test 2: Backlog Analysis[/bold blue]")

    result = run_agent(
        "Analyze the existing Jira tickets in the backlog and suggest "
        "any missing tickets, identify dependencies between them, and "
        "flag potential risks."
    )

    _validate_result(result, "Backlog Analysis")
    display_tickets(result)
    return result

def _validate_result(result: TicketGenerationResult, test_name: str):
    """Validate the structure of a TicketGenerationResult."""
    checks = []

    # Check 1: Result is not None
    checks.append(("Result exists", result is not None))

    # Check 2: Has tickets
    checks.append(("Has tickets", result.ticket_count > 0))

    # Check 3: No error
    checks.append(("No errors", result.error is None))

    # Check 4: Source query preserved
    checks.append(("Source query set", len(result.source_query) > 0))

    # Check 5: Timestamp present
    checks.append(("Timestamp present", len(result.generated_at) > 0))

    # Check 6: Each ticket has required fields
    all_valid = True
    for ticket in result.tickets:
        if not ticket.title or not ticket.type:
            all_valid = False
            break
    checks.append(("All tickets have title+type", all_valid))

    # Check 7: Story points are valid Fibonacci
    valid_sp = {1, 2, 3, 5, 8, 13, 21}
    sp_valid = all(t.story_points in valid_sp for t in result.tickets) if result.tickets else True
    checks.append(("Story points are Fibonacci", sp_valid))

    # Display results
    console.print(f"\n[bold]Validation: {test_name}[/bold]")
    all_passed = True
    for name, passed in checks:
        icon = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
        console.print(f"  {icon} {name}")
        if not passed:
            all_passed = False

    if all_passed:
        console.print(f"\n[bold green]All checks passed for {test_name}[/bold green]\n")
    else:
        console.print(f"\n[bold yellow]Some checks failed for {test_name}[/bold yellow]\n")

    # Print JSON output for inspection
    if result.tickets:
        console.print("[dim]First ticket as JSON:[/dim]")
        ticket_json = result.tickets[0].model_dump()
        console.print(json.dumps(ticket_json, indent=2, ensure_ascii=False))

    return all_passed

def main():
    console.print(
        Panel(
            "[bold magenta]Jira AI Copilot - Agent Pipeline Test Suite[/bold magenta]",
            title="Test Suite",
            border_style="magenta",
        )
    )

    # Run test 1
    result1 = test_payment_feature()

    console.print(
        Panel(
            f"[bold green]Tests complete![/bold green]\n"
            f"Test 1: {result1.ticket_count} tickets generated",
            title="Test Results",
            border_style="green",
        )
    )

if __name__ == "__main__":
    main()
