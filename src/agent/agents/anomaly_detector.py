from __future__ import annotations
import json
from typing import Optional, List, Any
from pydantic import BaseModel, Field, ConfigDict
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_mistralai.chat_models import ChatMistralAI
from langchain_huggingface import HuggingFaceEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

from src.models.state import WorkspaceState
from src.utils.console import console
from src.models.ticket import JiraTicket

class Conflict(BaseModel):
    model_config = ConfigDict(strict=True)
    withTicket: str = Field(..., description="The title or reference of the conflicting ticket")
    reason: str = Field(..., description="Reason for the conflict")

class AnomalyFlag(BaseModel):
    model_config = ConfigDict(strict=True)
    ticketRef: str
    isDuplicate: bool
    duplicateOf: Optional[str] = None
    duplicateReason: Optional[str] = Field(default=None, description="Explanation why it is flagged as duplicate")
    conflicts: list[Conflict] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    riskLevel: str = Field(default="LOW", description="LOW | MEDIUM | HIGH")

class AnomalyDetectorAgent:
    """
    Agent 2: Anomaly Detector
    Checks for duplicates using embeddings and Qdrant, and detects logic 
    conflicts/dependencies using a single LLM prompt.
    """
    def __init__(self):
        # We can configure this later; hardcoded defaults for now.
        self.embeddings = HuggingFaceEmbeddings(model_name="nomic-ai/nomic-embed-text-v1.5", model_kwargs={"trust_remote_code": True})
        # Qdrant client to hook into existing
        import os
        self.qdrant_client = QdrantClient(os.getenv("QDRANT_URL", "http://localhost:6333"))
        self.collection_name = os.getenv("QDRANT_COLLECTION", "jira_copilot")
        self.llm = ChatMistralAI(model="mistral-large-latest", temperature=0, max_retries=3, timeout=60)

    def run(self, state: WorkspaceState) -> dict:
        console.print("[bold green]>> Agent: Anomaly Detector[/bold green]")
        
        # Standard fallback to ensure we catch tickets whether in 'draft_tickets' or 'tickets'
        tickets: list[JiraTicket] = state.get("tickets", [])
        if not tickets and "draft_tickets" in state:
            # We assume draft_tickets is a dict array. Map it.
            tickets = [JiraTicket(**t) for t in state["draft_tickets"]]
            
        if not tickets:
            console.print("[yellow]No tickets found to process for anomalies.[/yellow]")
            return {"anomaly_flags": []}

        anomaly_flags_output: list[dict] = []
        
        # 1. DUPLICATE DETECTION 
        # Embed current batch (in memory for local comparisons)
        ticket_texts = [f"{t.title}. {t.description}" for t in tickets]
        try:
            curr_embeddings = np.array(self.embeddings.embed_documents(ticket_texts))
        except Exception as e:
            console.print(f"[red]Warning: Embedding failed, skipping dup detect: {e}[/red]")
            curr_embeddings = None

        # Build initial flags and check local + DB duplicates
        for i, ticket in enumerate(tickets):
            is_dup = False
            dup_of = None
            
            if curr_embeddings is not None:
                # 1a. Local batch compare (are two draft tickets identical?)
                for j, other_ticket in enumerate(tickets):
                    if i != j:
                        sim = cosine_similarity([curr_embeddings[i]], [curr_embeddings[j]])[0][0]
                        if sim > 0.85:
                            is_dup = True
                            dup_of = other_ticket.title
                            break
                            
                # 1b. Vector DB compare (if not already local duplicate)
                if not is_dup:
                    try:
                        hits = self.qdrant_client.search(
                            collection_name=self.collection_name,
                            query_vector=curr_embeddings[i].tolist(),
                            limit=1,
                            score_threshold=0.85
                        )
                        if hits:
                            is_dup = True
                            dup_of = hits[0].payload.get("source", "Existing Ticket")
                    except Exception as e:
                        pass # Ignore DB failures (like missing collection)

            if is_dup:
                dup_reason = f"Cosine similarity of {sim:.2f} with local context" if curr_embeddings is not None and j is not None else "Similarity match with database ticket"
                console.print(f"[yellow]⚠️ DUPLICATE DETECTED:[/yellow] '{ticket.title}' is a dup of '{dup_of}'.")
            else:
                dup_reason = None
            
            anomaly_flags_output.append({
                "ticketRef": ticket.title,
                "isDuplicate": is_dup,
                "duplicateOf": dup_of,
                "duplicateReason": dup_reason,
                "conflicts": [],
                "dependencies": ticket.dependencies,
                "riskLevel": "LOW"
            })

        # 2. FUNCTIONAL INCONSISTENCY & DEPENDENCY DETECTION (LLM)
        llm_input_text = "Here are the tickets:\n\n"
        for i, t in enumerate(tickets):
            llm_input_text += f"---\n[{i}] TITLE: {t.title}\nDESCRIPTION: {t.description}\nAC: {t.acceptance_criteria}\n"
            
        sys_prompt = (
            "You are a technical lead. Analyze the provided user stories to identify functional conflicts, "
            "overlapping scopes, and implicit ordering dependencies between them.\n"
            "Each conflict or dependency MUST have a clear specific explanation/reason attached to it.\n"
            "Respond ONLY with valid JSON matching exactly this schema for a list of tickets:\n"
            "{\n"
            '  "tickets": [\n'
            "    {\n"
            '      "ticketRef": "EXACT TITLE FROM PROMPT",\n'
            '      "conflicts": [{"withTicket": "EXACT TITLE", "reason": "Clear explanation of conflict"}],\n'
            '      "dependencies": ["PAY-XXX Auth System (Explanation of why it depends)"],\n'
            '      "riskLevel": "LOW" | "MEDIUM" | "HIGH" (HIGH if >2 dependencies or critical conflicts)\n'
            "    }\n"
            "  ]\n"
            "}"
        )
        
        console.print("[cyan]Querying LLM for logic inconsistencies & DAG...[/cyan]")
        try:
            # Requires Mistral with json_mode=True
            llm_with_json = self.llm.bind(response_format={"type": "json_object"})
            response = llm_with_json.invoke([
                SystemMessage(content=sys_prompt),
                HumanMessage(content=llm_input_text)
            ])
            llm_data = json.loads(response.content)
            
            # Merge LLM insight into the flag objects
            for llm_tick in llm_data.get("tickets", []):
                for flag in anomaly_flags_output:
                    if flag["ticketRef"] == llm_tick.get("ticketRef"):
                        flag["conflicts"] = llm_tick.get("conflicts", [])
                        
                        # Merge dependencies carefully
                        existing_deps = set(flag["dependencies"])
                        existing_deps.update(llm_tick.get("dependencies", []))
                        flag["dependencies"] = list(existing_deps)
                        
                        flag["riskLevel"] = llm_tick.get("riskLevel", "LOW")
        except Exception as e:
            console.print(f"[red]Warning: LLM Anomaly detection failed: {e}[/red]")
            
        # Pydantic Structural Validation
        valid_flags = []
        for f in anomaly_flags_output:
            try:
                valid = AnomalyFlag(**f)
                valid_flags.append(valid.model_dump())
            except Exception as v_err:
                console.print(f"[red]Validation error on ticket {f.get('ticketRef')}: {v_err}[/red]")
                # Fallback purely for pipeline survival
                valid_flags.append(f)

        return {"anomaly_flags": valid_flags}

def anomaly_detector_agent(state: WorkspaceState) -> dict:
    """Wrapper function for LangGraph node execution."""
    agent = AnomalyDetectorAgent()
    return agent.run(state)

