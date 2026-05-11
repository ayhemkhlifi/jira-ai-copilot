"""
Jira AI Copilot - RAG pipeline (ingestion, retrieval, generation).
"""

from __future__ import annotations

import hashlib
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_text_splitters import RecursiveCharacterTextSplitter

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_mistralai import ChatMistralAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    VectorParams,
)

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

from src.utils.console import console

DATA_DIR: Path = _PROJECT_ROOT / os.getenv("DATA_DIR", "data")

QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "jira_copilot")

EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "mistral-embed")
if "nomic" in EMBEDDING_MODEL.lower():
    EMBEDDING_DIMENSION: int = 768
else:
    EMBEDDING_DIMENSION: int = 1024

LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "mistral")
LLM_MODEL: str = os.getenv("LLM_MODEL", "mistral-medium")

CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "200"))
RETRIEVER_K: int = int(os.getenv("RETRIEVER_K", "8"))
RETRIEVER_SEARCH_TYPE: str = os.getenv("RETRIEVER_SEARCH_TYPE", "mmr")
RETRIEVER_FETCH_K: int = int(os.getenv("RETRIEVER_FETCH_K", "24"))


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _file_content_hash(filepath: Path) -> str:
    """Compute SHA-256 hash of one source file."""
    sha = hashlib.sha256()
    with open(filepath, "rb") as file_handle:
        for block in iter(lambda: file_handle.read(8192), b""):
            sha.update(block)
    return sha.hexdigest()


def _determine_document_type(filename: str) -> str:
    """Infer a document type label from filename."""
    name = filename.lower()
    if "meeting" in name or "notes" in name:
        return "meeting_notes"
    if "retro" in name:
        return "retrospective"
    if "spec" in name or "requirement" in name:
        return "specification"
    if "backlog" in name:
        return "backlog"
    if "sprint" in name and "retro" not in name:
        return "sprint_report"
    if "test" in name or "recette" in name:
        return "test_plan"
    return "general"


def _determine_project(filename: str) -> str:
    """Infer project tag from filename."""
    name = filename.lower()
    if "payment" in name:
        return "payment-feature"
    if "auth" in name:
        return "authentication"
    if "search" in name:
        return "search-feature"
    return "jira-copilot"


def _enrich_metadata(doc: Document, source_path: Path, content_hash: str) -> Document:
    """Attach normalized metadata used for filtering and traceability."""
    filename = source_path.name
    doc.metadata.update(
        {
            "source_filename": filename,
            "file_extension": source_path.suffix.lower(),
            "document_type": _determine_document_type(filename),
            "project": _determine_project(filename),
            "ingestion_date": datetime.now(timezone.utc).isoformat(),
            "content_hash": content_hash,
            "char_count": len(doc.page_content),
        }
    )
    return doc


def _get_embeddings():
    """Create embedding model instance."""
    if "mistral" in EMBEDDING_MODEL.lower():
        from langchain_mistralai import MistralAIEmbeddings
        return MistralAIEmbeddings(model=EMBEDDING_MODEL)
    else:
        # For HuggingFace models like nomic-embed-text-v2-moe or bge-m3
        return HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={'trust_remote_code': True}
        )

def _get_llm() -> ChatMistralAI:
    """Create chat model instance."""
    if LLM_PROVIDER != "mistral":
        raise ValueError(f"Unsupported LLM provider: {LLM_PROVIDER}")
    return ChatMistralAI(
        model=LLM_MODEL,
        temperature=0.3,
        max_tokens=4096,
    )


def _get_qdrant_client() -> QdrantClient:
    """Create Qdrant client."""
    return QdrantClient(url=QDRANT_URL)


def _build_qdrant_filter(
    project: str | None = None,
    document_types: Sequence[str] | None = None,
) -> Filter | None:
    """Build optional metadata filter for retrieval."""
    conditions: list[FieldCondition] = []

    if project:
        conditions.append(
            FieldCondition(
                key="metadata.project",
                match=MatchValue(value=project),
            )
        )

    if document_types:
        if len(document_types) == 1:
            conditions.append(
                FieldCondition(
                    key="metadata.document_type",
                    match=MatchValue(value=document_types[0]),
                )
            )
        else:
            conditions.append(
                FieldCondition(
                    key="metadata.document_type",
                    match=MatchAny(any=list(document_types)),
                )
            )

    if not conditions:
        return None
    return Filter(must=conditions)


def _scan_existing_collection(
    client: QdrantClient,
) -> Tuple[set[str], Dict[str, set[str]], Dict[str, set[str]]]:
    """
    Scan collection and return:
    - existing chunk ids
    - {source_filename -> content_hashes}
    - {source_filename -> chunk_ids}
    """
    chunk_ids: set[str] = set()
    source_hashes: Dict[str, set[str]] = defaultdict(set)
    source_chunk_ids: Dict[str, set[str]] = defaultdict(set)

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

            chunk_id = metadata.get("chunk_id")
            if chunk_id:
                chunk_ids.add(chunk_id)

            source_filename = metadata.get("source_filename")
            content_hash = metadata.get("content_hash")
            document_type = metadata.get("document_type")
            if source_filename and content_hash and document_type != "jira_ticket":
                source_hashes[source_filename].add(content_hash)
                if chunk_id:
                    source_chunk_ids[source_filename].add(chunk_id)

        if next_offset is None:
            break
        offset = next_offset

    return chunk_ids, source_hashes, source_chunk_ids


def _delete_points_by_source_filename(client: QdrantClient, source_filename: str) -> None:
    """Delete all chunks for one source file from Qdrant."""
    client.delete(
        collection_name=QDRANT_COLLECTION,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="metadata.source_filename",
                    match=MatchValue(value=source_filename),
                )
            ]
        ),
        wait=True,
    )


# -----------------------------------------------------------------------------
# Document ingestion
# -----------------------------------------------------------------------------


def ingest_documents(
    data_dir: Path | None = None,
    force_reingest: bool = False,
) -> int:
    """
    Ingest TXT/PDF documents into Qdrant with incremental behavior.

    Refresh behavior:
    - unchanged sources are skipped
    - changed sources are deleted then re-indexed
    """
    data_dir = data_dir or DATA_DIR
    if not data_dir.exists():
        console.print(f"[red]X Data directory not found: {data_dir}[/red]")
        sys.exit(1)

    console.print(
        Panel(
            f"[bold cyan]Starting ingestion from:[/bold cyan]\n{data_dir}",
            title="Ingestion Pipeline",
            border_style="cyan",
        )
    )

    raw_docs: List[Document] = []
    txt_files = list(data_dir.glob("**/*.txt"))
    pdf_files = list(data_dir.glob("**/*.pdf"))

    for txt_file in txt_files:
        try:
            loaded_docs = TextLoader(str(txt_file), encoding="utf-8").load()
            raw_docs.extend(loaded_docs)
            console.print(f"  [green]OK[/green] Loaded TXT: {txt_file.name}")
        except Exception as error:
            console.print(f"  [red]X[/red] Failed to load {txt_file.name}: {error}")

    for pdf_file in pdf_files:
        try:
            loaded_docs = PyPDFLoader(str(pdf_file)).load()
            raw_docs.extend(loaded_docs)
            console.print(f"  [green]OK[/green] Loaded PDF: {pdf_file.name}")
        except Exception as error:
            console.print(f"  [red]X[/red] Failed to load {pdf_file.name}: {error}")

    if not raw_docs:
        console.print("[yellow]! No source documents found to ingest.[/yellow]")
        return 0

    console.print(f"\n  Raw documents loaded: [bold]{len(raw_docs)}[/bold]")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
        is_separator_regex=False,
    )
    chunks: List[Document] = splitter.split_documents(raw_docs)
    console.print(f"  Chunks produced: [bold]{len(chunks)}[/bold]")

    # Enrich metadata and create stable per-chunk ids.
    source_hash_cache: dict[Path, str] = {}
    source_current_hashes: dict[str, str] = {}
    expected_chunks_per_source: dict[str, int] = defaultdict(int)
    for chunk in chunks:
        source_path = Path(chunk.metadata.get("source", "unknown"))
        if source_path not in source_hash_cache and source_path.exists():
            source_hash_cache[source_path] = _file_content_hash(source_path)

        content_hash = source_hash_cache.get(
            source_path,
            hashlib.sha256(chunk.page_content.encode()).hexdigest(),
        )
        _enrich_metadata(chunk, source_path, content_hash)

        # Keep chunk id backward-compatible with previous ingestion runs.
        chunk_id = hashlib.sha256((content_hash + chunk.page_content).encode()).hexdigest()
        chunk.metadata["chunk_id"] = chunk_id
        source_current_hashes[source_path.name] = content_hash
        expected_chunks_per_source[source_path.name] += 1

    client = _get_qdrant_client()
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
        existing_chunk_ids: set[str] = set()
        source_hashes: Dict[str, set[str]] = {}
        source_chunk_ids: Dict[str, set[str]] = {}
    else:
        console.print("  Collection exists - scanning existing chunks")
        existing_chunk_ids, source_hashes, source_chunk_ids = _scan_existing_collection(client)

    # If source hash changed, or if duplicates are detected, clear and refresh.
    stale_sources: list[str] = []
    for source_filename, current_hash in source_current_hashes.items():
        known_hashes = source_hashes.get(source_filename, set())
        existing_count = len(source_chunk_ids.get(source_filename, set()))
        expected_count = expected_chunks_per_source.get(source_filename, 0)

        if known_hashes and current_hash not in known_hashes:
            stale_sources.append(source_filename)
            continue

        # Cleanup path for old duplicate points caused by previous chunk-id schemes.
        if known_hashes and expected_count > 0 and existing_count > expected_count:
            stale_sources.append(source_filename)

    for source_filename in stale_sources:
        try:
            _delete_points_by_source_filename(client, source_filename)
            for stale_chunk_id in source_chunk_ids.get(source_filename, set()):
                existing_chunk_ids.discard(stale_chunk_id)
            console.print(f"  Refreshed changed source: {source_filename}")
        except Exception as error:
            console.print(
                f"  [yellow]! Could not refresh source {source_filename}: {error}[/yellow]"
            )

    new_chunks: list[Document] = []
    for chunk in chunks:
        if chunk.metadata.get("chunk_id") not in existing_chunk_ids:
            new_chunks.append(chunk)

    if not new_chunks:
        console.print("[green]OK All documents already up-to-date.[/green]")
        return 0

    console.print(
        f"  Chunks to ingest: [bold]{len(new_chunks)}[/bold] "
        f"(skipped {len(chunks) - len(new_chunks)} existing)"
    )

    embeddings = _get_embeddings()
    console.print("  Generating embeddings and writing to Qdrant...")

    QdrantVectorStore.from_documents(
        documents=new_chunks,
        embedding=embeddings,
        url=QDRANT_URL,
        collection_name=QDRANT_COLLECTION,
        force_recreate=False,
    )

    console.print(
        Panel(
            f"[bold green]OK Successfully ingested {len(new_chunks)} chunks "
            f"into '{QDRANT_COLLECTION}'[/bold green]",
            title="Ingestion Complete",
            border_style="green",
        )
    )
    return len(new_chunks)


# -----------------------------------------------------------------------------
# Retrieval and generation
# -----------------------------------------------------------------------------


_SYSTEM_PROMPT = """\
You are an expert Agile delivery assistant and Jira copilot.
Analyze the provided context and generate well-structured Jira ticket proposals.

Each ticket must include:
1) Title
2) Type
3) Description
4) Acceptance criteria (Given/When/Then style)
5) Priority (with rationale)
6) Story points (Fibonacci)
7) Labels
8) Dependencies
9) Component

Rules:
- Use only the provided context.
- Do not invent missing facts.
- Flag risks, conflicts, and ambiguities.
- Avoid duplicates.

CONTEXT:
{context}

USER REQUEST:
{question}
"""


def _format_context(docs: Iterable[Document]) -> str:
    """Format retrieved documents as traceable prompt context."""
    formatted_parts: list[str] = []
    for index, doc in enumerate(docs, 1):
        metadata = doc.metadata
        header = (
            f"--- Chunk {index} ---\n"
            f"Source: {metadata.get('source_filename', 'unknown')} | "
            f"Type: {metadata.get('document_type', 'general')} | "
            f"Project: {metadata.get('project', 'N/A')}\n"
        )
        formatted_parts.append(header + doc.page_content)
    return "\n\n".join(formatted_parts)


def create_vectorstore() -> QdrantVectorStore:
    """Open existing Qdrant collection as LangChain vector store."""
    embeddings = _get_embeddings()
    return QdrantVectorStore.from_existing_collection(
        embedding=embeddings,
        url=QDRANT_URL,
        collection_name=QDRANT_COLLECTION,
    )


def create_retriever(
    vectorstore: QdrantVectorStore,
    project: str | None = None,
    document_types: Sequence[str] | None = None,
    k: int = RETRIEVER_K,
    search_type: str = RETRIEVER_SEARCH_TYPE,
):
    """Create retriever with optional metadata filters."""
    q_filter = _build_qdrant_filter(project=project, document_types=document_types)

    search_kwargs: dict = {"k": k}
    if search_type == "mmr":
        search_kwargs["fetch_k"] = max(RETRIEVER_FETCH_K, k * 3)
    if q_filter is not None:
        search_kwargs["filter"] = q_filter

    return vectorstore.as_retriever(
        search_type=search_type,
        search_kwargs=search_kwargs,
    )


def create_rag_chain(
    project: str | None = None,
    document_types: Sequence[str] | None = None,
    k: int = RETRIEVER_K,
    search_type: str = RETRIEVER_SEARCH_TYPE,
):
    """
    Build RAG chain: retriever -> prompt -> LLM -> text output.
    """
    console.print(
        Panel(
            "[bold cyan]Building RAG chain...[/bold cyan]",
            title="Chain Assembly",
            border_style="cyan",
        )
    )

    vectorstore = create_vectorstore()
    retriever = create_retriever(
        vectorstore=vectorstore,
        project=project,
        document_types=document_types,
        k=k,
        search_type=search_type,
    )
    console.print(
        f"  [green]OK[/green] Retriever ready (type={search_type}, k={k})"
    )

    prompt = ChatPromptTemplate.from_template(_SYSTEM_PROMPT)
    llm = _get_llm()
    console.print(f"  [green]OK[/green] LLM initialized ({LLM_PROVIDER}/{LLM_MODEL})")

    chain = (
        {
            "context": retriever | _format_context,
            "question": RunnablePassthrough(),
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    console.print(
        Panel(
            "[bold green]OK RAG chain assembled successfully[/bold green]",
            title="Chain Ready",
            border_style="green",
        )
    )
    return chain, retriever


def preview_retrieval(
    query: str,
    project: str | None = None,
    document_types: Sequence[str] | None = None,
    k: int = RETRIEVER_K,
) -> List[Document]:
    """
    Inspect top-k retrieval hits and scores for one query.
    Useful to validate retrieval quality before agent orchestration.
    """
    vectorstore = create_vectorstore()
    q_filter = _build_qdrant_filter(project=project, document_types=document_types)
    results = vectorstore.similarity_search_with_score(
        query=query,
        k=k,
        filter=q_filter,
    )

    table = Table(title="Retrieval Preview", border_style="cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("Score", width=10)
    table.add_column("Type", width=16)
    table.add_column("Source", width=36)
    table.add_column("Preview", width=60)

    documents: list[Document] = []
    for rank, (doc, score) in enumerate(results, 1):
        metadata = doc.metadata
        documents.append(doc)
        table.add_row(
            str(rank),
            f"{score:.4f}",
            metadata.get("document_type", "?"),
            metadata.get("source_filename", "?"),
            doc.page_content[:60].replace("\n", " ") + "...",
        )
    console.print(table)
    return documents


# -----------------------------------------------------------------------------
# Main demo
# -----------------------------------------------------------------------------


def main() -> None:
    """End-to-end RAG demo."""
    console.print(
        Panel(
            "[bold magenta]Jira AI Copilot - RAG Pipeline Demo[/bold magenta]\n"
            f"Qdrant: {QDRANT_URL} | Collection: {QDRANT_COLLECTION}\n"
            f"LLM: {LLM_PROVIDER}/{LLM_MODEL} | Embeddings: {EMBEDDING_MODEL}",
            title="Jira AI Copilot",
            border_style="magenta",
            expand=False,
        )
    )

    console.rule("[bold blue]Phase 1 - Document Ingestion[/bold blue]")
    ingest_documents()

    console.rule("[bold blue]Phase 2 - RAG Chain Construction[/bold blue]")
    chain, retriever = create_rag_chain()

    console.rule("[bold blue]Phase 3 - Query Execution[/bold blue]")
    test_query = (
        "Generate Jira tickets from yesterday's meeting notes about the new "
        "payment feature. Include user stories, technical tasks, and any "
        "security-related tickets."
    )
    console.print(f"\n[bold yellow]Query:[/bold yellow]\n{test_query}\n")
    console.print("[dim]Retrieving context and generating answer...[/dim]\n")

    response = chain.invoke(test_query)
    console.print(
        Panel(
            response,
            title="Generated Jira Tickets",
            border_style="green",
            expand=True,
            padding=(1, 2),
        )
    )

    console.rule("[bold blue]Retrieved Context[/bold blue]")
    retrieved_docs = retriever.invoke(test_query)
    for index, doc in enumerate(retrieved_docs, 1):
        source = doc.metadata.get("source_filename", "?")
        doc_type = doc.metadata.get("document_type", "?")
        preview = doc.page_content[:120].replace("\n", " ")
        console.print(f"  [{index}] [cyan]{source}[/cyan] ({doc_type}) - {preview}...")

    console.print(
        Panel(
            "[bold green]Pipeline execution complete[/bold green]",
            title="Done",
            border_style="green",
        )
    )


if __name__ == "__main__":
    main()
