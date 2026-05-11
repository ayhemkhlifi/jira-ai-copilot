from __future__ import annotations
import os
import time
from typing import Any
from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from src.models.state import WorkspaceState
from src.utils.console import console

LLM_MODEL = os.getenv("LLM_MODEL", "mistral-medium")

class SupervisorAgent:
    """
    Supervisor Agent: Analyzes the request, classifies the task type.
    """
    def __init__(self):
        self.llm = ChatMistralAI(
            model=LLM_MODEL,
            temperature=0,
            timeout=30
        )

    def run(self, state: WorkspaceState) -> dict:
        console.print("[bold magenta]>> Agent: Supervisor[/bold magenta]")
        user_request = state.get("user_request", "").strip()
        
        # Define the prompt for the LLM to classify the task type
        prompt = ChatPromptTemplate.from_template(
            "You are an AI assistant orchestrating a Jira Agile Copilot. "
            "Your job is to classify the user's incoming request into exactly ONE of the following categories:\n"
            "- 'generation': The user wants to create, generate, or write new Jira tickets based on context.\n"
            "- 'estimation': The user wants to estimate story points, effort, or time for existing tickets.\n"
            "- 'analysis': The user wants to analyze the backlog, review duplicates, check for anomalies, or summarize status.\n\n"
            "Respond ONLY with the exact category name (generation, estimation, or analysis), in lowercase, with no other text or punctuation.\n\n"
            "User Request: {user_request}"
        )
        
        # Build the chain
        chain = prompt | self.llm | StrOutputParser()
        
        try:
            raw_classification = chain.invoke({"user_request": user_request}).strip().lower()
            
            # Fallback mapping if LLM returns something messy
            if "estimation" in raw_classification:
                task_type = "estimation"
            elif "analysis" in raw_classification:
                task_type = "analysis"
            else:
                task_type = "generation"  # Default to generation
                
            console.print(f"   [dim]Supervisor classified task as: [bold]{task_type}[/bold][/dim]")
            
        except Exception as e:
            console.print(f"   [yellow]Supervisor classification failed (using default 'generation'): {e}[/yellow]")
            task_type = "generation"
        
        return {
            "task_type": task_type,
            "retry_count": 0,
            "metadata": {
                **state.get("metadata", {}),
                "supervisor_classified": True
            }
        }
