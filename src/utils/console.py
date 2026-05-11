"""
Shared console utilities for the Jira AI Copilot.
Handles Windows UTF-8 encoding fix and provides a shared Rich console.
"""

import sys
import os

# Fix Windows terminal encoding — runs ONCE at import time
if sys.platform == "win32" and not os.environ.get("_JIRA_COPILOT_ENCODING_FIXED"):
    import io
    try:
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding="utf-8", errors="replace"
        )
    except Exception:
        pass  # Already wrapped or no buffer available
    os.environ["_JIRA_COPILOT_ENCODING_FIXED"] = "1"

from rich.console import Console

console = Console(force_terminal=True)
