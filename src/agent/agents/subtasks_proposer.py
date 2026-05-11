import json
from pydantic import BaseModel, Field, ConfigDict
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_mistralai.chat_models import ChatMistralAI
from src.models.state import WorkspaceState
from src.utils.console import console

class Subtask(BaseModel):
    model_config = ConfigDict(strict=True)
    title: str
    assignedRole: str
    effortFraction: float
    order: int
    dependsOn: list[int]

class SubtasksProposerAgent:
    def __init__(self):
        self.llm = ChatMistralAI(model="mistral-large-latest", temperature=0)

    def run(self, state: WorkspaceState) -> dict:
        console.print("[bold green]>> Agent: Subtasks Proposer[/bold green]")
        
        tickets = state.get("tickets", [])
        if not tickets and "draft_tickets" in state:
            from src.models.ticket import JiraTicket
            tickets = [JiraTicket(**t) for t in state["draft_tickets"]]
            
        estimations = state.get("estimations", [])
        est_map = {e["ticketRef"]: e["pertEstimate"] for e in estimations}
        
        all_subtasks = []
        for ticket in tickets:
            sp = est_map.get(ticket.title, 0)
            if sp <= 5:
                all_subtasks.append([])
                continue
                
            sys_prompt = (
                "Decompose this user story into ordered subtasks.\n"
                "IMPORTANT: Assign correct roles (Frontend for UI/React/Views, Backend for APIs/DB/Webhooks, QA for testing, DevOps for infra, Design for UI/UX).\n"
                "Return JSON strictly matching:\n"
                "{ 'subtasks': [\n"
                "  { 'title': '...', 'assignedRole': 'Frontend|Backend|QA|DevOps|Design', 'effortFraction': 0.5, 'order': 1, 'dependsOn': [] }\n"
                "] }"
            )
            try:
                resp = self.llm.bind(response_format={"type": "json_object"}).invoke([
                    SystemMessage(content=sys_prompt),
                    HumanMessage(content=f"Ticket: {ticket.title}\n{ticket.description}")
                ])
                data = json.loads(resp.content)
                tasks = data.get("subtasks", [])
                
                # Normalize strictly to sum to 1.0 safely
                raw_total = sum(t.get("effortFraction", 0) for t in tasks)
                valid_tasks = []
                accumulated = 0.0
                
                for i, t in enumerate(tasks):
                    raw_val = t.get("effortFraction", 0)
                    if raw_total > 0:
                        if i == len(tasks) - 1:
                            # Last task picks up the remainder to guarantee exactly 1.0
                            calc_fraction = round(1.0 - accumulated, 2)
                        else:
                            calc_fraction = round(raw_val / raw_total, 2)
                            accumulated += calc_fraction
                        t["effortFraction"] = max(0.01, calc_fraction) # Avoid 0 or negative
                    valid_tasks.append(Subtask(**t).model_dump())
                    
                all_subtasks.append(valid_tasks)
            except Exception as e:
                console.print(f"[red]Subtasks err: {e}[/red]")
                all_subtasks.append([])
                
        return {"subtasks": all_subtasks}

def subtasks_proposer_node(state: WorkspaceState) -> dict:
    return SubtasksProposerAgent().run(state)
