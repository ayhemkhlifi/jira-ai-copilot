"""
Jira AI Copilot - Jira ticket ingestion into Qdrant.

This module connects to Jira Cloud, fetches project issues, converts each issue
to a LangChain Document, and stores vectors in Qdrant for retrieval.
"""

from __future__ import annotations

import hashlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from langchain_core.documents import Document
from langchain_mistralai import MistralAIEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    VectorParams,
)

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

# Keep Windows terminal stable for rich output.
from src.utils.console import console

def _env(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else default


JIRA_BASE_URL: str = _env("JIRA_BASE_URL")
JIRA_EMAIL: str = _env("JIRA_EMAIL")
JIRA_API_TOKEN: str = _env("JIRA_API_TOKEN")
JIRA_PROJECT_KEY: str = _env("JIRA_PROJECT_KEY")
JIRA_PAGE_SIZE: int = int(os.getenv("JIRA_PAGE_SIZE", "100"))

QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "jira_copilot")

EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "mistral-embed")
if "nomic" in EMBEDDING_MODEL.lower():
    EMBEDDING_DIMENSION: int = 768
else:
    EMBEDDING_DIMENSION: int = 1024
REQUEST_TIMEOUT_S: int = int(os.getenv("REQUEST_TIMEOUT_S", "30"))


# -----------------------------------------------------------------------------
# Jira REST helpers
# -----------------------------------------------------------------------------


def _get_jira_auth() -> tuple[str, str]:
    """Return basic auth tuple for Jira Cloud API."""
    if not all([JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN]):
        console.print(
            "[red]X Missing Jira credentials in .env.[/red]\n"
            "  Required: JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN"
        )
        sys.exit(1)
    return JIRA_EMAIL, JIRA_API_TOKEN


def fetch_jira_tickets(
    project_key: str | None = None,
    max_results: int | None = None,
) -> List[Dict[str, Any]]:
    """
    Fetch Jira issues for a project with pagination.

    Parameters
    ----------
    project_key:
        Jira project key (for example "PAY").
    max_results:
        Optional hard cap for total issues returned. ``None`` fetches all pages.
    """
    project_key = project_key or JIRA_PROJECT_KEY
    if not project_key:
        console.print("[red]X No JIRA_PROJECT_KEY set in .env[/red]")
        sys.exit(1)

    auth = _get_jira_auth()
    jql = f"project = {project_key} ORDER BY created DESC"
    fields = (
        "summary,description,status,priority,issuetype,assignee,"
        "reporter,created,updated,labels,components,comment,"
        "subtasks,issuelinks,customfield_10016"
    )
    base_url = JIRA_BASE_URL.rstrip("/")
    jql_url = f"{base_url}/rest/api/3/search/jql"
    legacy_url = f"{base_url}/rest/api/3/search"

    console.print(f"  Fetching tickets from Jira project: [cyan]{project_key}[/cyan]")
    console.print(f"  Preferred URL: {jql_url}")
    console.print(f"  JQL: {jql}")

    try:
        issues, total_available = _fetch_via_search_jql(
            url=jql_url,
            auth=auth,
            jql=jql,
            fields=fields,
            max_results=max_results,
        )
    except requests.exceptions.HTTPError as error:
        status = error.response.status_code if error.response is not None else None
        if status in {404, 405}:
            console.print(
                "  [yellow]! /search/jql unavailable on this Jira instance. "
                "Falling back to /search.[/yellow]"
            )
            issues, total_available = _fetch_via_legacy_search(
                url=legacy_url,
                auth=auth,
                jql=jql,
                fields=fields,
                max_results=max_results,
            )
        else:
            console.print(f"[red]X Jira API error: {error}[/red]")
            if error.response is not None:
                console.print(f"  Response: {error.response.text[:500]}")
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        console.print(f"[red]X Cannot connect to Jira at {JIRA_BASE_URL}[/red]")
        sys.exit(1)
    except requests.exceptions.Timeout:
        console.print(
            f"[red]X Jira API request timed out after {REQUEST_TIMEOUT_S}s[/red]"
        )
        sys.exit(1)

    total_text = str(total_available) if total_available is not None else "unknown"
    console.print(
        f"  [green]OK[/green] Fetched [bold]{len(issues)}[/bold] tickets "
        f"(total available: {total_text})"
    )
    if not issues:
        console.print(
            f"  [yellow]! Jira returned no issues for project '{project_key}'. "
            "Check JIRA_PROJECT_KEY and Jira project permissions.[/yellow]"
        )
    return issues


def _fetch_via_search_jql(
    url: str,
    auth: tuple[str, str],
    jql: str,
    fields: str,
    max_results: int | None,
) -> tuple[list[dict[str, Any]], int | None]:
    """
    Fetch issues using Jira /search/jql endpoint (token-based pagination).
    """
    issues: list[dict[str, Any]] = []
    next_page_token: str | None = None

    while True:
        page_size = JIRA_PAGE_SIZE
        if max_results is not None:
            remaining = max_results - len(issues)
            if remaining <= 0:
                break
            page_size = min(page_size, remaining)

        params = {
            "jql": jql,
            "maxResults": page_size,
            "fields": fields,
        }
        if next_page_token:
            params["nextPageToken"] = next_page_token

        response = requests.get(url, params=params, auth=auth, timeout=REQUEST_TIMEOUT_S)
        response.raise_for_status()

        payload = response.json()
        page_issues = payload.get("issues", [])
        issues.extend(page_issues)

        next_page_token = payload.get("nextPageToken")
        is_last = payload.get("isLast")
        if not page_issues or is_last is True or not next_page_token:
            break

    # /search/jql does not currently return total count in this Jira mode.
    return issues, None


def _fetch_via_legacy_search(
    url: str,
    auth: tuple[str, str],
    jql: str,
    fields: str,
    max_results: int | None,
) -> tuple[list[dict[str, Any]], int | None]:
    """
    Fetch issues using legacy Jira /search endpoint (startAt pagination).
    """
    issues: list[dict[str, Any]] = []
    total_available: int | None = None
    start_at = 0

    while True:
        page_size = JIRA_PAGE_SIZE
        if max_results is not None:
            remaining = max_results - len(issues)
            if remaining <= 0:
                break
            page_size = min(page_size, remaining)

        params = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": page_size,
            "fields": fields,
        }
        response = requests.get(url, params=params, auth=auth, timeout=REQUEST_TIMEOUT_S)
        response.raise_for_status()

        payload = response.json()
        page_issues = payload.get("issues", [])
        issues.extend(page_issues)

        if total_available is None and isinstance(payload.get("total"), int):
            total_available = payload["total"]

        if not page_issues:
            break

        start_at += len(page_issues)
        if total_available is not None and start_at >= total_available:
            break
        if len(page_issues) < page_size:
            break

    return issues, total_available


# -----------------------------------------------------------------------------
# Ticket -> Document conversion
# -----------------------------------------------------------------------------


def _extract_text_from_adf(adf_content: Any) -> str:
    """Extract plain text recursively from Atlassian Document Format."""
    if adf_content is None:
        return ""
    if isinstance(adf_content, str):
        return adf_content

    text_parts: list[str] = []

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "text":
                text_parts.append(node.get("text", ""))
            for child in node.get("content", []):
                _walk(child)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(adf_content)
    return "\n".join(text_parts)


def _extract_comments(issue: Dict[str, Any]) -> str:
    """Extract Jira comments as plain text."""
    comments_field = issue.get("fields", {}).get("comment", {})
    comments = comments_field.get("comments", [])
    if not comments:
        return ""

    comment_texts: list[str] = []
    for comment in comments:
        author = comment.get("author", {}).get("displayName", "Unknown")
        body = _extract_text_from_adf(comment.get("body", ""))
        created = comment.get("created", "")[:10]
        comment_texts.append(f"[{created}] {author}: {body}")

    return "\n".join(comment_texts)


def ticket_to_document(issue: Dict[str, Any]) -> Document:
    """Convert a raw Jira issue payload to a LangChain Document."""
    fields = issue.get("fields", {})
    key = issue.get("key", "UNKNOWN")

    summary = fields.get("summary", "No summary")
    description = _extract_text_from_adf(fields.get("description"))
    status = fields.get("status", {}).get("name", "Unknown")
    priority = fields.get("priority", {}).get("name", "Medium") if fields.get("priority") else "Medium"
    issue_type = fields.get("issuetype", {}).get("name", "Task")
    assignee = fields.get("assignee", {}).get("displayName", "Unassigned") if fields.get("assignee") else "Unassigned"
    reporter = fields.get("reporter", {}).get("displayName", "Unknown") if fields.get("reporter") else "Unknown"
    created = fields.get("created", "")[:10]
    updated = fields.get("updated", "")[:10]
    labels = fields.get("labels", [])
    components = [component.get("name", "") for component in fields.get("components", [])]
    story_points = fields.get("customfield_10016")
    comments = _extract_comments(issue)

    subtasks = fields.get("subtasks", [])
    subtask_text = ""
    if subtasks:
        lines = [f"  - [{st.get('key')}] {st.get('fields', {}).get('summary', '')}" for st in subtasks]
        subtask_text = "\nSubtasks:\n" + "\n".join(lines)

    issue_links = fields.get("issuelinks", [])
    deps_text = ""
    if issue_links:
        dep_lines: list[str] = []
        for link in issue_links:
            link_type = link.get("type", {}).get("outward", "relates to")
            if "outwardIssue" in link:
                dep_key = link["outwardIssue"].get("key", "?")
                dep_summary = link["outwardIssue"].get("fields", {}).get("summary", "")
                dep_lines.append(f"  - {link_type} [{dep_key}] {dep_summary}")
            elif "inwardIssue" in link:
                inward_type = link.get("type", {}).get("inward", "relates to")
                dep_key = link["inwardIssue"].get("key", "?")
                dep_summary = link["inwardIssue"].get("fields", {}).get("summary", "")
                dep_lines.append(f"  - {inward_type} [{dep_key}] {dep_summary}")
        if dep_lines:
            deps_text = "\nDependencies:\n" + "\n".join(dep_lines)

    page_content = f"""JIRA Ticket: {key}
Title: {summary}
Type: {issue_type}
Status: {status}
Priority: {priority}
Assignee: {assignee}
Reporter: {reporter}
Created: {created}
Updated: {updated}
Story Points: {story_points if story_points else 'Not estimated'}
Labels: {', '.join(labels) if labels else 'None'}
Components: {', '.join(components) if components else 'None'}

Description:
{description if description else 'No description provided.'}
{subtask_text}
{deps_text}
"""
    if comments:
        page_content += f"\nComments:\n{comments}\n"

    metadata = {
        "source": "jira",
        "source_filename": f"jira_ticket_{key}",
        "jira_key": key,
        "jira_summary": summary,
        "jira_type": issue_type,
        "jira_status": status,
        "jira_priority": priority,
        "jira_assignee": assignee,
        "jira_reporter": reporter,
        "jira_created": created,
        "jira_updated": updated,
        "jira_story_points": story_points if story_points else 0,
        "jira_labels": ", ".join(labels),
        "jira_components": ", ".join(components),
        "document_type": "jira_ticket",
        "project": key.split("-", 1)[0],
        "ingestion_date": datetime.now(timezone.utc).isoformat(),
        "content_hash": hashlib.sha256(page_content.encode()).hexdigest(),
        "char_count": len(page_content),
    }
    return Document(page_content=page_content, metadata=metadata)


# -----------------------------------------------------------------------------
# Qdrant storage
# -----------------------------------------------------------------------------


def ingest_jira_tickets(
    tickets: List[Document],
    force_reingest: bool = False,
) -> int:
    """
    Embed and store Jira ticket documents into Qdrant.

    The function performs incremental sync:
    - New ticket keys are inserted.
    - Existing keys with changed content are refreshed.
    - Unchanged keys are skipped.
    """
    if not tickets:
        console.print("[yellow]! No tickets to ingest.[/yellow]")
        return 0

    client = QdrantClient(url=QDRANT_URL)

    existing_collections = [collection.name for collection in client.get_collections().collections]
    collection_exists = QDRANT_COLLECTION in existing_collections

    if force_reingest and collection_exists:
        console.print(f"  [yellow]Dropping collection: {QDRANT_COLLECTION}[/yellow]")
        client.delete_collection(QDRANT_COLLECTION)
        collection_exists = False

    if not collection_exists:
        console.print(f"  Creating collection: {QDRANT_COLLECTION}")
        client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(
                size=EMBEDDING_DIMENSION,
                distance=Distance.COSINE,
            ),
        )

    existing_ticket_hashes = _get_existing_ticket_hashes(client)

    to_ingest: list[Document] = []
    updated_keys: set[str] = set()
    new_count = 0
    updated_count = 0
    skipped_count = 0

    for ticket in tickets:
        jira_key = ticket.metadata.get("jira_key")
        content_hash = ticket.metadata.get("content_hash")

        if not jira_key:
            to_ingest.append(ticket)
            new_count += 1
            continue

        current_hash = existing_ticket_hashes.get(jira_key)
        if current_hash is None:
            to_ingest.append(ticket)
            new_count += 1
        elif current_hash != content_hash:
            to_ingest.append(ticket)
            updated_count += 1
            updated_keys.add(jira_key)
        else:
            skipped_count += 1

    if not to_ingest:
        console.print("[green]OK All Jira tickets already up-to-date.[/green]")
        return 0

    if updated_keys:
        console.print(
            f"  Refreshing {len(updated_keys)} changed ticket(s) in Qdrant"
        )
        for jira_key in sorted(updated_keys):
            _delete_existing_ticket_points(client, jira_key)

    console.print(
        f"  Tickets to ingest: [bold]{len(to_ingest)}[/bold] "
        f"(new={new_count}, updated={updated_count}, skipped={skipped_count})"
    )

    if "mistral" in EMBEDDING_MODEL.lower():
        embeddings = MistralAIEmbeddings(model=EMBEDDING_MODEL)
    else:
        embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={'trust_remote_code': True}
        )
    console.print("  Generating embeddings and storing in Qdrant...")

    QdrantVectorStore.from_documents(
        documents=to_ingest,
        embedding=embeddings,
        url=QDRANT_URL,
        collection_name=QDRANT_COLLECTION,
        force_recreate=False,
    )

    console.print(
        Panel(
            f"[bold green]OK Successfully ingested {len(to_ingest)} Jira ticket(s) "
            f"into '{QDRANT_COLLECTION}'[/bold green]",
            title="Jira Ingestion Complete",
            border_style="green",
        )
    )
    return len(to_ingest)


def _get_existing_ticket_hashes(client: QdrantClient) -> Dict[str, str]:
    """Scan Qdrant and collect {jira_key -> content_hash} for all ticket points."""
    ticket_hashes: dict[str, str] = {}
    try:
        offset = None
        while True:
            points, next_offset = client.scroll(
                collection_name=QDRANT_COLLECTION,
                limit=200,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in points:
                payload = point.payload or {}
                metadata = payload.get("metadata", payload)
                jira_key = metadata.get("jira_key")
                if jira_key:
                    ticket_hashes[jira_key] = metadata.get("content_hash", "")
            if next_offset is None:
                break
            offset = next_offset
    except Exception as error:
        console.print(
            f"  [yellow]! Could not read existing Jira hashes: {error}[/yellow]"
        )
    return ticket_hashes


def _delete_existing_ticket_points(client: QdrantClient, jira_key: str) -> None:
    """Delete all Qdrant points for one Jira key before re-indexing updates."""
    try:
        client.delete(
            collection_name=QDRANT_COLLECTION,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="metadata.jira_key",
                        match=MatchValue(value=jira_key),
                    )
                ]
            ),
            wait=True,
        )
    except Exception as error:
        console.print(
            f"  [yellow]! Could not delete existing points for {jira_key}: {error}[/yellow]"
        )


# -----------------------------------------------------------------------------
# Display helper
# -----------------------------------------------------------------------------


def display_tickets_table(issues: List[Dict[str, Any]]) -> None:
    """Display fetched Jira issues in a summary table."""
    table = Table(
        title="Fetched Jira Tickets",
        show_lines=True,
        border_style="cyan",
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Key", style="bold cyan", width=12)
    table.add_column("Type", width=12)
    table.add_column("Priority", width=12)
    table.add_column("Status", width=12)
    table.add_column("Summary", width=56)

    for index, issue in enumerate(issues, 1):
        fields = issue.get("fields", {})
        table.add_row(
            str(index),
            issue.get("key", "?"),
            fields.get("issuetype", {}).get("name", "?"),
            fields.get("priority", {}).get("name", "?") if fields.get("priority") else "?",
            fields.get("status", {}).get("name", "?"),
            fields.get("summary", "?")[:56],
        )

    console.print(table)


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def main() -> None:
    """Run end-to-end Jira ingestion."""
    console.print(
        Panel(
            "[bold magenta]Jira Ticket Ingestion Pipeline[/bold magenta]\n"
            f"Jira: {JIRA_BASE_URL} | Project: {JIRA_PROJECT_KEY}\n"
            f"Qdrant: {QDRANT_URL} | Collection: {QDRANT_COLLECTION}",
            title="Jira -> Qdrant",
            border_style="magenta",
            expand=False,
        )
    )

    console.rule("[bold blue]Phase 1 - Fetch Jira Tickets[/bold blue]")
    issues = fetch_jira_tickets()
    if not issues:
        console.print(
            "[yellow]! No Jira tickets were fetched, so ingestion will stop here.[/yellow]"
        )
        return
    display_tickets_table(issues)

    console.rule("[bold blue]Phase 2 - Convert to Documents[/bold blue]")
    documents: list[Document] = []
    for issue in issues:
        document = ticket_to_document(issue)
        documents.append(document)
        console.print(
            f"  [green]OK[/green] {document.metadata['jira_key']} - "
            f"{document.metadata['jira_summary'][:60]}"
        )

    console.print(f"\n  Total documents created: [bold]{len(documents)}[/bold]")

    console.rule("[bold blue]Phase 3 - Store in Qdrant[/bold blue]")
    ingested_count = ingest_jira_tickets(documents)

    console.print(
        Panel(
            f"[bold green]Pipeline complete[/bold green]\n"
            f"Tickets fetched: {len(issues)}\n"
            f"Documents created: {len(documents)}\n"
            f"Tickets ingested/updated: {ingested_count}",
            title="Done",
            border_style="green",
        )
    )


if __name__ == "__main__":
    main()
