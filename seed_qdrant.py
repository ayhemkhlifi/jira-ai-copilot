"""
=============================================================================
Jira AI Copilot — Qdrant Cloud Seeding Script
=============================================================================

Seeds a remote Qdrant Cloud instance with:
  1. Local document data (meeting notes, specs, etc.)
  2. Existing Jira tickets from your Jira Cloud project

Run this BEFORE deploying to production so the RAG context is populated
and ticket quality is good from the first use.

Usage:
    # Against local Qdrant (default):
    python seed_qdrant.py

    # Against Qdrant Cloud:
    python seed_qdrant.py --qdrant-url https://xxx.cloud.qdrant.io:6333 --qdrant-api-key YOUR_KEY

    # Skip Jira tickets (only ingest local docs):
    python seed_qdrant.py --skip-jira

    # Force re-ingest everything (drops existing data):
    python seed_qdrant.py --force
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Ensure project root is importable
_PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_PROJECT_ROOT))

load_dotenv(_PROJECT_ROOT / ".env")

from src.utils.console import console
from rich.panel import Panel


def main():
    parser = argparse.ArgumentParser(
        description="Seed Qdrant (local or cloud) with documents and Jira tickets."
    )
    parser.add_argument(
        "--qdrant-url",
        default=None,
        help="Qdrant URL (overrides QDRANT_URL from .env)",
    )
    parser.add_argument(
        "--qdrant-api-key",
        default=None,
        help="Qdrant API key (overrides QDRANT_API_KEY from .env)",
    )
    parser.add_argument(
        "--skip-jira",
        action="store_true",
        help="Skip Jira ticket ingestion (only ingest local documents)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-ingest (drops and recreates the collection)",
    )
    args = parser.parse_args()

    # Override env vars if CLI args provided
    if args.qdrant_url:
        os.environ["QDRANT_URL"] = args.qdrant_url
    if args.qdrant_api_key:
        os.environ["QDRANT_API_KEY"] = args.qdrant_api_key

    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key = os.getenv("QDRANT_API_KEY", "")
    collection = os.getenv("QDRANT_COLLECTION", "jira_copilot_nomic")

    console.print(
        Panel(
            f"[bold magenta]Qdrant Seeding Script[/bold magenta]\n"
            f"Target: {qdrant_url}\n"
            f"Collection: {collection}\n"
            f"API Key: {'set' if qdrant_api_key else 'not set (local mode)'}\n"
            f"Force: {args.force}\n"
            f"Skip Jira: {args.skip_jira}",
            title="Seed Configuration",
            border_style="magenta",
        )
    )

    # ------------------------------------------------------------------
    # Step 1: Ingest local documents (meeting notes, specs, etc.)
    # ------------------------------------------------------------------
    console.rule("[bold blue]Step 1 — Ingest Local Documents[/bold blue]")

    from src.rag_pipeline import ingest_documents

    doc_count = ingest_documents(force_reingest=args.force)
    console.print(f"  Local documents ingested: [bold]{doc_count}[/bold]")

    # ------------------------------------------------------------------
    # Step 2: Ingest Jira tickets
    # ------------------------------------------------------------------
    if not args.skip_jira:
        console.rule("[bold blue]Step 2 — Ingest Jira Tickets[/bold blue]")

        from src.jira_ingestion import (
            fetch_jira_tickets,
            ticket_to_document,
            ingest_jira_tickets,
            display_tickets_table,
        )

        issues = fetch_jira_tickets()
        if issues:
            display_tickets_table(issues)
            documents = [ticket_to_document(issue) for issue in issues]
            ticket_count = ingest_jira_tickets(documents, force_reingest=args.force)
            console.print(f"  Jira tickets ingested: [bold]{ticket_count}[/bold]")
        else:
            console.print("  [yellow]No Jira tickets found to ingest.[/yellow]")
    else:
        console.print("\n  [dim]Skipping Jira ticket ingestion (--skip-jira)[/dim]")

    # ------------------------------------------------------------------
    # Step 3: Verify
    # ------------------------------------------------------------------
    console.rule("[bold blue]Step 3 — Verify Collection[/bold blue]")

    from qdrant_client import QdrantClient

    client_kwargs = {"url": qdrant_url, "timeout": 10}
    if qdrant_api_key:
        client_kwargs["api_key"] = qdrant_api_key

    client = QdrantClient(**client_kwargs)
    try:
        info = client.get_collection(collection)
        console.print(
            Panel(
                f"[bold green]Seeding complete![/bold green]\n"
                f"Collection: {collection}\n"
                f"Total points: {info.points_count}\n"
                f"Vectors size: {info.config.params.vectors.size}\n"
                f"\nYour Qdrant instance is ready for production deployment.",
                title="✓ Success",
                border_style="green",
            )
        )
    except Exception as e:
        console.print(f"[red]Could not verify collection: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
