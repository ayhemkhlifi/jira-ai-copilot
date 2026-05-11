from __future__ import annotations
import os
import time
from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from src.models.state import WorkspaceState
from src.utils.console import console

LLM_MODEL = os.getenv("LLM_MODEL", "mistral-medium")

_TICKET_GENERATION_PROMPT = """\
You are an expert Agile delivery assistant and Jira copilot.
Analyze the provided context documents and generate well-structured Jira tickets.

You MUST respond with a valid JSON array of ticket objects. Each ticket must have:
- "title": Clear, concise, action-oriented (starts with a verb)
- "type": One of "Epic", "Story", "Task", "Bug", "Sub-task"
- "description": Detailed functional description ONLY (move NFRs to non_functional_requirements)
- "acceptance_criteria": Array of testable criteria (Given/When/Then format)
- "non_functional_requirements": Array of strings covering PCI compliance, concurrency, tokenization, performance, etc.
- "priority": One of "Critical", "High", "Medium", "Low"
- "priority_justification": Why this priority was chosen
- "story_points": Fibonacci estimate (1, 2, 3, 5, 8, 13)
- "labels": Array of categorization labels (e.g., ["payment", "stripe"])
- "dependencies": Array of related/blocking ticket references (strings)
- "component": One of "Backend", "Frontend", "Infrastructure", "QA", "Design", "DevOps"
- "subtasks": Array of strings (sub-task titles)
- "risks": Array of strings

Rules:
- Base analysis ONLY on the provided context. Do not invent facts.
- Generate a maximum of 3-5 high-priority tickets to prevent overwhelming the system.
- Acceptance criteria and subtasks MUST be simple strings, not objects.
- Flag risks, conflicts, and ambiguities.
- Avoid duplicate or overlapping tickets.
- Group related tickets logically.
- Suggest sub-tasks when a ticket exceeds 8 story points.
- ALWAYS escape control characters like newlines (use \\n). Never put real line breaks inside JSON strings.

IMPORTANT: Return ONLY a valid JSON array. No markdown, no extra text, no code fences.

---

CONTEXT DOCUMENTS:
{context}

---

USER REQUEST: {user_request}

JSON ARRAY:
"""

class TicketGeneratorAgent:
    """
    Agent 1: Ticket Generator
    Generates structured Jira tickets based on retrieved context.
    """
    def __init__(self):
        self.llm = ChatMistralAI(
            model=LLM_MODEL,
            temperature=0.2,
            max_tokens=8192,
            timeout=300, # Increased timeout to prevent read timeouts on large outputs
            max_retries=3
        )

    def run(self, state: WorkspaceState) -> dict:
        console.print("[cyan]>> Agent: Ticket Generator[/cyan]")
        start = time.time()

        context = state.get("context", "")
        user_request = state["user_request"]

        prompt = ChatPromptTemplate.from_template(_TICKET_GENERATION_PROMPT)
        chain = prompt | self.llm | StrOutputParser()

        try:
            raw_output = chain.invoke({
                "context": context,
                "user_request": user_request,
            })
            
            elapsed = time.time() - start
            console.print(f"   LLM generated {len(raw_output)} chars in {elapsed:.2f}s")

            meta = state.get("metadata", {})
            meta["generation_time_s"] = round(elapsed, 2)
            
            return {
                "raw_llm_output": raw_output,
                "metadata": meta,
            }
        except Exception as e:
            return {"error": f"Generation failed: {str(e)}", "raw_llm_output": ""}
