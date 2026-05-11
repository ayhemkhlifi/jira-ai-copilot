import json
from pydantic import BaseModel, Field, ConfigDict
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_mistralai.chat_models import ChatMistralAI
from src.models.state import WorkspaceState
from src.utils.console import console
import os
from qdrant_client import QdrantClient
from langchain_huggingface import HuggingFaceEmbeddings

class Neighbor(BaseModel):
    title: str
    sp: int
    similarity: float

class Estimation(BaseModel):
    model_config = ConfigDict(strict=True)
    ticketRef: str
    min: int
    probable: int
    max: int
    pertEstimate: int
    confidence: float
    rationale: str
    retrievedNeighbors: list[Neighbor] = Field(default_factory=list)

def round_to_fibonacci(n: float) -> int:
    fib = [1, 2, 3, 5, 8, 13, 21]
    return min(fib, key=lambda x: abs(x - n))

class EffortEstimatorAgent:
    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(model_name="nomic-ai/nomic-embed-text-v1.5", model_kwargs={"trust_remote_code": True})
        self.qdrant_client = QdrantClient(os.getenv("QDRANT_URL", "http://localhost:6333"))
        self.collection_name = os.getenv("QDRANT_COLLECTION", "jira_copilot")
        self.llm = ChatMistralAI(model="mistral-large-latest", temperature=0)

    def run(self, state: WorkspaceState) -> dict:
        console.print("[bold green]>> Agent: Effort Estimator[/bold green]")
        
        tickets = state.get("tickets", [])
        if not tickets and "draft_tickets" in state:
            from src.models.ticket import JiraTicket
            tickets = [JiraTicket(**t) for t in state["draft_tickets"]]
            
        anomaly_flags = state.get("anomaly_flags", [])
        dup_titles = {f["ticketRef"] for f in anomaly_flags if f.get("isDuplicate")}
        
        estimations = []
        for ticket in tickets:
            if ticket.title in dup_titles:
                continue
                
            ticket_text = f"{ticket.title}. {ticket.description}. {ticket.acceptance_criteria}"
            emb = self.embeddings.embed_query(ticket_text)
            
            neighbors = []
            try:
                hits = self.qdrant_client.search(
                    collection_name=self.collection_name, query_vector=emb, limit=5
                )
                for h in hits:
                    sp = h.payload.get("story_points", 3)
                    neighbors.append(Neighbor(title=h.payload.get("source", "Historical"), sp=int(sp), similarity=h.score))
            except:
                pass
                
            if not neighbors:
                neighbors = [Neighbor(title="Fallback", sp=3, similarity=0.5)]
                
            sps = [n.sp for n in neighbors]
            sps.sort()
            min_sp = min(sps)
            max_sp = max(sps)
            
            # Simple weighted probable
            weights = [n.similarity for n in neighbors]
            if sum(weights) > 0:
                probable = sum(n.sp * n.similarity for n in neighbors) / sum(weights)
            else:
                probable = sum(sps) / len(sps)
                
            pert = (min_sp + 4*probable + max_sp) / 6
            fib_pert = round_to_fibonacci(pert)
            
            sys_prompt = (
                "You are an Agile coach. Provide a SINGLE solid recommended SP estimate "
                "or explain clearly why a wide range is needed (e.g. '8 SP if X, "
                "21 SP if Y'). The 'rationale' must also briefly justify the "
                "confidence score. Return JSON: {'rationale': '...', 'confidence': 0.8}"
            )
            user_prompt = f"Ticket: {ticket.title}\nDescription: {ticket.description}\nProposed SP: {fib_pert}\nHistorical SPs: {sps}"
            
            try:
                resp = self.llm.bind(response_format={"type": "json_object"}).invoke([SystemMessage(content=sys_prompt), HumanMessage(content=user_prompt)])
                llm_data = json.loads(resp.content)
                conf = float(llm_data.get("confidence", 0.7))
                rat = llm_data.get("rationale", "Estimated based on historical context.")
            except:
                conf = 0.5
                rat = "Fallback rationale"
                
            estimations.append({
                "ticketRef": ticket.title,
                "min": min_sp,
                "probable": int(probable),
                "max": max_sp,
                "pertEstimate": fib_pert,
                "confidence": conf,
                "rationale": rat,
                "retrievedNeighbors": [n.model_dump() for n in neighbors]
            })
            
        return {"estimations": estimations}

def effort_estimator_node(state: WorkspaceState) -> dict:
    return EffortEstimatorAgent().run(state)
