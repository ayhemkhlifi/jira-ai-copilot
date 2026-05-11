
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.append(str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from src.rag_pipeline import ingest_documents, create_vectorstore, create_retriever, _format_context
from src.utils.console import console
from rich.panel import Panel

def test_ingestion_and_retrieval():
    console.print(Panel("[bold cyan]STEP 1: Testing Ingestion[/bold cyan]"))
    try:
        # Changed force_reingest to False to avoid dropping the collection
        count = ingest_documents(force_reingest=False)
        console.print(f"[bold green]SUCCESS:[/bold green] Ingested {count} chunks (or handled existing). Check output above.")
    except Exception as e:
        console.print(f"[bold red]FAILED Ingestion:[/bold red] {e}")
        return

    console.print(Panel("[bold cyan]STEP 2: Testing Retrieval[/bold cyan]"))
    query = "What are the key points in the payment feature meeting notes?"
    try:
        vs = create_vectorstore()
        retriever = create_retriever(vs, k=4)
        docs = retriever.invoke(query)
        context = _format_context(docs)
        console.print(f"[bold green]SUCCESS:[/bold green] Retrieved {len(docs)} documents for query: '{query}'")
        console.print("\n[dim]Context snippet:[/dim]")
        console.print(context[:500] + "...")
    except Exception as e:
        console.print(f"[bold red]FAILED Retrieval:[/bold red] {e}")
        return

if __name__ == "__main__":
    test_ingestion_and_retrieval()
