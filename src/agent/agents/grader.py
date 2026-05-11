from src.models.state import WorkspaceState
from src.utils.console import console

def grader_node(state: WorkspaceState) -> dict:
    console.print("[bold green]>> Node: Grader[/bold green]")
    errors = []
    confidence_min = 1.0
    
    estimations = state.get("estimations", [])
    if not estimations:
        errors.append("No estimations found")
    else:
        for e in estimations:
            conf = e.get("confidence", 1.0)
            if conf < confidence_min:
                confidence_min = conf
                
    subtasks = state.get("subtasks", [])
    test_cases = state.get("test_cases", [])
    
    forced_review = confidence_min < 0.5
    
    return {
        "grader_errors": errors,
        "confidence_min": confidence_min,
        "forced_review": forced_review,
        "retry_count": state.get("retry_count", 0) + 1
    }
