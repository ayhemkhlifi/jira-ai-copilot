import json
from pydantic import BaseModel, Field, ConfigDict
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_mistralai.chat_models import ChatMistralAI
from src.models.state import WorkspaceState
from src.utils.console import console

class TestCase(BaseModel):
    model_config = ConfigDict(strict=True)
    id: str
    type: str
    title: str
    preconditions: list[str]
    steps: list[str]
    expectedResult: str
    criticality: str
    executionType: str

class TestCaseGeneratorAgent:
    def __init__(self):
        self.llm = ChatMistralAI(model="mistral-large-latest", temperature=0)

    def run(self, state: WorkspaceState) -> dict:
        console.print("[bold green]>> Agent: Test Case Generator[/bold green]")
        
        tickets = state.get("tickets", [])
        if not tickets and "draft_tickets" in state:
            from src.models.ticket import JiraTicket
            tickets = [JiraTicket(**t) for t in state["draft_tickets"]]
            
        anomaly_flags = state.get("anomaly_flags", [])
        dup_titles = {f["ticketRef"] for f in anomaly_flags if f.get("isDuplicate")}
        
        all_tcs = []
        for ticket in tickets:
            if ticket.title in dup_titles:
                all_tcs.append([])
                continue
                
            sys_prompt = (
                "Generate test cases strictly tied to this ticket's acceptance criteria! Do NOT hallucinate testing features that are not explicitly stated in the ACs.\n"
                "Return JSON strictly matching:\n"
                "{ 'testCases': [\n"
                "  { 'id': 'TC-001', 'type': 'nominal|error|limit', 'title': '...', 'preconditions': [], 'steps': [], 'expectedResult': '...', 'criticality': 'major', 'executionType': 'manual' }\n"
                "] }"
            )
            try:
                resp = self.llm.bind(response_format={"type": "json_object"}).invoke([
                    SystemMessage(content=sys_prompt),
                    HumanMessage(content=f"Ticket: {ticket.title}\nACs: {ticket.acceptance_criteria}")
                ])
                data = json.loads(resp.content)
                tcs = data.get("testCases", [])
                
                valid_tcs = [TestCase(**t).model_dump() for t in tcs]
                all_tcs.append(valid_tcs)
            except Exception as e:
                console.print(f"[red]TC err: {e}[/red]")
                all_tcs.append([])
                
        return {"test_cases": all_tcs}

def test_case_generator_node(state: WorkspaceState) -> dict:
    return TestCaseGeneratorAgent().run(state)
