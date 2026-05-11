from __future__ import annotations
import time
from src.models.state import WorkspaceState
from src.rag_pipeline import create_vectorstore, create_retriever, _format_context, RETRIEVER_K
from src.utils.console import console

def retrieve_context_logic(state: WorkspaceState) -> dict:
    """Retrieval logic moved from node for modularity."""
    console.print("[cyan]>> Logic: Retrieving Context[/cyan]")
    start = time.time()
    user_request = state["user_request"]

    try:
        vectorstore = create_vectorstore()
        retriever = create_retriever(vectorstore=vectorstore, k=RETRIEVER_K)
        docs = retriever.invoke(user_request)
        context = _format_context(docs)
        elapsed = time.time() - start

        console.print(f"   Retrieved {len(docs)} documents in {elapsed:.2f}s")
        return {
            "retrieved_docs": docs,
            "context": context,
            "metadata": {
                **state.get("metadata", {}),
                "retrieval_time_s": round(elapsed, 2),
                "docs_retrieved": len(docs),
            },
        }
    except Exception as e:
        console.print(f"   [bold red]Retrieval failed: {e}[/bold red]")
        return {"error": f"Retrieval failed: {str(e)}"}
